import time
import logging
import requests
from threading import Lock

import slacksocket.errors as errors
from .config import urls
from .models import User, Channel, DirItem

log = logging.getLogger('slacksocket')

class WebClient(requests.Session):
    """
    Minimal client for connecting to Slack web API and translating user/channel
    IDs to human-readable names
    """

    def __init__(self, token, timeout):
        self._token = token
        self._timeout = timeout
        self._users = Directory()
        self._channels = Directory()
        self._lock = Lock()
        super(WebClient, self).__init__()

    def login(self):
        """ perform API auth test returning user and team """
        log.debug('performing auth test')
        test = self._get(urls['test'])
        user = User({ 'name': test['user'], 'id': test['user_id'] })
        self._refresh()
        return test['team'], user

    def rtm_url(self):
        """ Retrieve a fresh websocket url from slack api """
        return self._get(urls['rtm'])['url']

    def open_im(self, user_id):
        res = self._post(urls['im.open'], user=user_id)
        return Channel({'name':user_id, 'id': res['channel']})

    def user(self, match):
        """ Return User object for a given Slack ID or name """
        if len(match) == 9 and match[0] == 'U':
            return self._lookup(User, 'id', match)
        return self._lookup(User, 'name', match)

    def channel(self, match):
        """ Return Channel object for a given Slack ID or name """
        if len(match) == 9 and match[0] in ('C','G','D'):
            return self._lookup(Channel, 'id', match)
        return self._lookup(Channel, 'name', match)

    #######
    # Internal Methods
    #######

    def _get(self, url, **params):
        return self._do('GET', url, **params)

    def _post(self, url, **params):
        return self._do('POST', url, **params)

    def _do(self, method, url, **params):
        start = time.time()
        params['token'] = self._token

        while True:
            if self._timeout > 0 and time.time() - start >= self._timeout:
                raise errors.TimeoutError('connection timeout exceeded')
            try:
                return self._do_once(method, url, **params)
            except errors.APIError as ex:
                raise ex
            except Exception as ex:
                log.error(ex)
                time.sleep(2)

    def _do_once(self, method, url, **params):
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
            raise RuntimeError('socket in migration state')

        raise errors.APIError('Error from slack api:\n%s' % res.text)

    def _get_pages(self, url, **params):
        params['cursor'] = ''

        while True:
            res = self._get(url, **params)
            if 'response_metadata' in res:
                params['cursor'] = res['response_metadata'].get('next_cursor')
            yield res
            if not params['cursor']:
                return

    def _lookup(self, stype, attr, val):
        if stype == User:
            sdir = self._users
        if stype == Channel:
            sdir = self._channels

        res = sdir.match(attr, val)
        if not res:
            # reload cache and try again
            self._refresh()
            res = sdir.match(attr, val)
        return res if res else DirItem({})

    def _refresh(self):
        """ refresh internal directory cache """
        log.debug('refreshing directory cache')
        self._users.update(list(self._user_gen()))
        self._channels.update(list(self._channel_gen()))

    def _user_gen(self):
        for page in self._get_pages(urls['users']):
            for data in page['members']:
                yield User(data)

    def _channel_gen(self):
        pages = self._get_pages(urls['convos'],
                types='public_channel,private_channel,mpim,im')

        for page in pages:
            for cdata in page['channels']:
                # if im channel, use username as name
                if cdata['id'][0] == 'D':
                    cdata['name'] = self._users.match('id', cdata['user']).name
                yield Channel(cdata)

class Directory(list):
    """ Generic locking store """
    def __init__(self):
        self._lock = Lock()

    def update(self, items):
        self._lock.acquire()
        self.clear()
        self += items
        self._lock.release()

    def match(self, attr, val):
        """ lookup object in directory with attribute matching value """
        self._lock.acquire()
        try:
            for x in self:
                if getattr(x, attr) == val:
                    return x
        finally:
            self._lock.release()
