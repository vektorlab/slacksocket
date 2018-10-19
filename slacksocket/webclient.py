import logging
import requests
from threading import Lock

import slacksocket.errors as errors
from .config import urls
from .cache import ObjectCache

log = logging.getLogger('slacksocket')

class WebClient(requests.Session):
    """
    Minimal client for connecting to Slack web API and translating user/channel
    IDs to human-readable names
    """

    def __init__(self, token):
        self._token = token

        self._users_lock = Lock() # used while reading/updating users cache
        self._channel_lock = Lock() # used while reading/updating channels cache

        self._ims = ObjectCache()
        self._users = ObjectCache()
        self._groups = ObjectCache()
        self._channels = ObjectCache()

        super(WebClient, self).__init__()

    def _get(self, url, method='GET', max_attempts=3, **params):
        if max_attempts <= 0:
            raise errors.APIError('max retries exceeded')

        params['token'] = self._token
        res = self.request(method, url, params=params, timeout=5)

        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise errors.APIError(e)

        rj = res.json()

        if rj['ok']:
            return rj

        # process error
        if rj['error'] == 'migration_in_progress':
            log.info('socket in migration state, retrying')
            time.sleep(2)
            return self.get(url, method, max_attempts-1, **params)
        else:
            raise errors.APIError('Error from slack api:\n%s' % res.text)

    def login(self):
        """ Login and initialize WebClient """
        # perform API auth test to get our user and team
        test = self._get(urls['test'])
        self.team, self.user = test['team'], test['user']

        # populate user/channel cache
        self._load_users()
        self._load_channels()

    def rtm_url(self):
        """ Retrieve a fresh websocket url from slack api """
        return self._get(urls['rtm'])['url']

    def im_channel(self, user_id):
        """
        Return channel ID for direct message with a given user. Create
        one if it does not exist.
        """
        im = self._ims.match('user', user_id)
        if im:
            return im['id']

        # open new im channel
        res = self._get(urls['im.open'], method='POST', user=user_id)
        return res['channel']

    def _load_users(self):
        """ update internal team users cache """
        self._users.update(self._get(urls['users'])['members'])

    def _load_channels(self):
        """ update internal team channels cache """
        self._ims.update(self._get(urls['ims'])['ims'])
        self._groups.update(self._get(urls['groups'])['groups'])
        self._channels.update(self._get(urls['channels'])['channels'])

    def id_to_name(self, idtype, sid):
        """ Look up a user or channel name from a provided Slack ID """
        if idtype == 'user':
            if sid == 'USLACKBOT':
                return "slackbot"
            user = self._lookup_user(sid=sid)
            return user.get('name', 'unknown')

        elif idtype == 'channel':
            channel, channel_type = self._lookup_channelish(sid=sid)
            if channel_type == 'im':
                return self.id_to_name('user', channel['user'])
            return channel.get('name', 'unknown')

        raise ValueError('idtype must be one of user, channel')

    def name_to_id(self, ntype, name):
        """ Look up a user or channel ID from a provided name """
        if ntype == 'user':
            if name == 'slackbot':
                return 'USLACKBOT'
            user = self._lookup_user(uname=name)
            return user.get('id', 'unknown')

        elif ntype == 'channel':
            channel, _ = self._lookup_channelish(cname=name)
            return channel.get('id', 'unknown')

        raise ValueError('ntype must be one of user, channel')

    def _lookup_user(self, uname=None, sid=None, retry=True):
        """ lookup a user object by name or id """
        match = {}

        if sid:
            match = self._users.match('id', sid)
        elif uname:
            match = self._users.match('name', uname)

        if not match and retry:
            # reload cache and retry in case this is a new user
            self._load_users()
            return self._lookup_user(uname, sid, False)

        return match

    def _lookup_channelish(self, cname=None, sid=None, retry=True):
        """ lookup a channel-like object (channel,group,etc.) by name or id """
        match = {}

        if sid:
            match = self._channels.match('id', sid)
            if match:
                return match, 'channel'

            match = self._groups.match('id', sid)
            if match:
                return match, 'group'

            match = self._ims.match('id', sid)
            if match:
                return match, 'im'

        elif cname:
            match = self._channels.match('name', cname)
            if match:
                return match, 'channel'

            match = self._groups.match('name', cname)
            if match:
                return match, 'group'

            uid = self.name_to_id('user', cname)
            match = self._ims.match('user', uid)
            if match:
                return match, 'im'

        # may be channel got created after the cache got loaded so reload the it one more time
        if retry:
            self._load_channels()
            return self._lookup_channelish(cname, sid, False)

        return match, 'unknown'
