import json
import logging
import websocket
import requests
import time
from threading import Thread, Lock

import slacksocket.errors as errors
from .config import slackurl, event_types
from .models import SlackEvent, SlackMsg

log = logging.getLogger('slacksocket')


class SlackClient(requests.Session):
    """
    A very small client for connecting to the Slack web API
    """
    def __init__(self, token):
        super(SlackClient, self).__init__()
        self.token = token
        self._attempts = 0

    def get_json(self, url, max_attempts=3):
        res = self._get(url)

        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise errors.SlackAPIError(e)

        rj = res.json()

        if rj['ok']:
            self._attempts = 0
            return rj

        # process error
        if rj['error'] == 'migration_in_progress':
            if self._attempts > max_attempts:
                raise errors.SlackAPIError('Max retries exceeded')
            log.info('socket in migration state, retrying')
            time.sleep(self._attempts)
            self._attempts += 1
            return self.get_json(url)
        else:
            raise errors.SlackAPIError('Error from slack api:\n %s' % res.text)


    def _post(self, url, payload=None):
        if payload:
            return self.post(url, params={'token': self.token}, payload=payload)
        return self.post(url, params={'token': self.token})

    def _get(self, url):
        return self.get(url, params={'token': self.token})

    def _check_response(self, res):
        return rj


class SlackSocket(object):
    """
    SlackSocket class provides a streaming interface to the Slack Real Time
    Messaging API
    params:
     - slacktoken(str): token to authenticate with slack
     - translate(bool): yield events with human-readable names
        rather than id. default true
     - event_filter(list): Slack event type(s) to filter by. Excluding a
            filter returns all slack events. See https://api.slack.com/events
            for a listing of valid event types.
    """

    def __init__(self, slacktoken, translate=True, event_filters='all'):
        if type(translate) != bool:
            raise TypeError('translate must be a boolean')
        self._validate_filters(event_filters)

        self._eventq = []
        self._sendq = []
        self.connected = False
        self._translate = translate
        self.event_filters = event_filters

        self.client = SlackClient(slacktoken)
        self.team, self.user = self._auth_test()

        # used while reading/updating loaded_user property
        self.load_user_lock = Lock()
        self._load_users()
        self.loaded_channels = {}
        # used while reading/updating loaded_channels property
        self.load_channel_lock = Lock()
        self._load_channels()

        self._thread = Thread(target=self._open)
        self._thread.daemon = True
        self._thread.start()

        # wait for websocket connection to be established before returning
        while not self.connected:
            time.sleep(.2)

    def get_event(self):
        """
        return a single event object or block until an event is
        received and return it.
        """
        # return or block until we have something to return
        while True:
            try:
                e = self._eventq.pop(0)
                return e
            except IndexError:
                time.sleep(.2)

    def events(self):
        """
        returns a blocking generator yielding Slack event objects
        params:
        """
        done = False
        while not done:
            try:
                e = self.get_event()
                yield (e)
            except KeyboardInterrupt:
                done = True
        self.close()

    def send_msg(self, text, channel_name=None, channel_id=None, confirm=True):
        """
        Send a message via Slack RTM socket, returning the message object
        after receiving a reply-to confirmation
        """
        if not channel_name and not channel_id:
            raise Exception('One of channel_id or channel_name \
                             parameters must be given')
        if channel_name:
            c = self._lookup_channel_by_name(channel_name)
            channel_id = c['channel_id']

        self._send_id += 1
        msg = SlackMsg(self._send_id, channel_id, text)
        self.ws.send(msg.json)

        if confirm:
            # Wait for confirmation our message was received
            for e in self.events():
                if 'reply_to' in e.event:
                    if e.event['reply_to'] == self._send_id:
                        msg.sent = True
                        msg.ts = e.ts
                        return msg
        else:
            return msg

    def close(self):
        self.ws.on_close = lambda ws: True
        self.ws.close()

    #######
    # Internal Methods
    #######

    def _open(self):
        # reset id for sending messages with each new socket
        self._send_id = 0
        self.ws = websocket.WebSocketApp(self._get_websocket_url(),
                                         on_message=self._event_handler,
                                         on_error=self._error_handler,
                                         on_open=self._open_handler,
                                         on_close=self._exit_handler)
        self.ws.run_forever()

    def _validate_filters(self, filters):
        if filters == 'all':
            filters = event_types

        if type(filters) != list:
            raise TypeError('filters must be given as a list')

        for f in filters:
            if f not in event_types:
                raise errors.SlackSocketEventNameError('unknown event type %s\n \
                             see https://api.slack.com/events' % filters)

    def _get_websocket_url(self):
        """
        Retrieve a fresh websocket url from slack api
        """
        return self.client.get_json(slackurl['rtm'])['url']

    def _auth_test(self):
        """
        Perform API auth test and get our user and team
        """
        test = self.client.get_json(slackurl['test'])

        if self._translate:
            return (test['team'], test['user'])
        else:
            return (test['team_id'], test['user_id'])

    def _lookup_user(self, user_id):
        """
        Look up a username from user id
        """
        if user_id == 'USLACKBOT':
            return "slackbot"

        name = self._find_user_name(user_id)

        # if the user is not found may be a new user got added after cache is loaded so reload it
        # one more time
        if not name:
            self._load_users()
            name = self._find_user_name(user_id)

        return name if name else "unknown"

    def _load_users(self):
        """
        Makes a call to slack service to fetch users and updates the loaded_users property
        """
        self.load_user_lock.acquire()
        try:
            self.loaded_users = self.client.get_json(slackurl['users'])['members']
        finally:
            self.load_user_lock.release()

    def _find_user_name(self, user_id):
        """
        Finds user's name by their id.
        """
        self.load_user_lock.acquire()
        try:
            users = self.loaded_users
        finally:
            self.load_user_lock.release()

        for user in users:
            if user['id'] == user_id:
                return user['name']

    def _lookup_channel_by_id(self, id):
        """
        Looks up a channel name from its id
        params:
         - id(str): The channel id to lookup
        """
        channel_type, matching = self._find_channel(['channels', 'groups', 'ims'],
                                                    "id",
                                                    id)

        # may be channel got created after the cache got loaded so reload the it one more time
        if not matching:
            self._load_channels()
            channel_type, matching = self._find_channel(['channels', 'groups', 'ims'],
                                                        "id",
                                                        id)

        if matching:
            channel = matching[0]
            if channel_type == 'ims':
                channel_name = self._lookup_user(channel['user'])
            else:
                channel_name = channel['name']

            return {'channel_type': channel_type,
                    'channel_name': channel_name}

        # if no matches were found
        return {'channel_type': 'unknown',
                'channel_name': 'unknown'}

    def _load_channels(self):
        """
        Makes a call to slack service to fetch all channel information.
        """
        self.load_channel_lock.acquire()
        try:
            for channel_type in ['channels', 'groups', 'ims']:
                channel_list = self.client.get_json(slackurl[channel_type])[channel_type]
                self.loaded_channels[channel_type] = channel_list
        finally:
            self.load_channel_lock.release()

    def _find_channel(self, channel_types, channel_key, value):
        """
        filters channels present in the cache using key and value
        """
        self.load_channel_lock.acquire()
        try:
            channels = self.loaded_channels
        finally:
            self.load_channel_lock.release()

        for channel_type, channel_list in channels.items():
            if channel_type not in channel_types:
                continue;
            matching = [c for c in channel_list if c[channel_key] == value]
            if matching:
                return channel_type, matching

        return None

    def _lookup_channel_by_name(self, name):
        """
        Look up a channel id from a given name
        params:
         - name(str): The channel name to lookup
        """
        channel_type, matching = self._find_channel(['channels', 'groups'],
                                                    "name",
                                                    name)
        # may be channel got created after the cache got loaded so reload the it one more time
        if not matching:
            self._load_channels()
            channel_type, matching = self._find_channel(['channels', 'groups'],
                                                        "name",
                                                        name)

        if matching:
            channel = matching[0]

            return {'channel_type': channel_type,
                    'channel_id': channel['id']}

        # if no matches were found
        return {'channel_type': 'unknown',
                'channel_id': 'unknown'}

    def _translate_event(self, event):
        """
        Translate all user and channel ids in an event to human-readable names
        """
        if 'user' in event.event:
            event.event['user'] = self._lookup_user(event.event['user'])

        if 'channel' in event.event:
            c = self._lookup_channel_by_id(event.event['channel'])
            event.event['channel'] = c['channel_name']

        event.mentions = [self._lookup_user(u) for u in event.mentions]

        return event

    #######
    # Websocket Handlers
    #######

    def _event_handler(self, ws, event_json):
        log.debug('event recieved: %s' % event_json)

        json_object = json.loads(event_json)

        if self.event_filters != "all" and json_object.get("type") not in self.event_filters:
            log.debug("Ignoring the event {} as it not matching event_filers {}"
                      .format(event_json, self.event_filters))
            return

        event = SlackEvent(json_object)

        # TODO: make use of ctype returned from _lookup_channel
        if self._translate:
            event = self._translate_event(event)

        self._eventq.append(event)

    def _open_handler(self, ws):
        log.info('websocket connection established')
        self.connected = True
        self.connect_ts = time.time()

    def _error_handler(self, ws, error):
        log.critical('websocket error:\n %s' % error)

    def _exit_handler(self, ws):
        log.warn('websocket connection closed')
        # Don't attempt reconnect if our last attempt was less than 30s ago
        if (time.time() - self.connect_ts) < 30:
            raise errors.SlackSocketConnectionError(
                'Failed to establish a websocket connection'
            )
        log.warn('attempting to reconnect')
        self._thread = Thread(target=self._open)
        self._thread.start()
