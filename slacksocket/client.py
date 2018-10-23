import ssl
import json
import time
import signal
import logging
import websocket
from threading import Thread

try:
    import queue as Queue # python3
except ImportError:
    import Queue # python2

import slacksocket.errors as errors
from .config import event_types
from .models import SlackEvent, SlackMsg
from .webclient import WebClient
from .directory import Directory

log = logging.getLogger('slacksocket')

STATE_STOPPED = 0
STATE_INITIALIZING = 1
STATE_INITIALIZED = 2
STATE_CONNECTING = 3
STATE_CONNECTED = 4

class SlackSocket(object):
    """
    SlackSocket class provides a streaming interface to the Slack Real Time
    Messaging API
    params:
     - slacktoken(str): token to authenticate with slack
     - event_filter(list): Optional Slack event type(s) to filter by. Excluding a
            filter returns all slack events. See https://api.slack.com/events
            for a listing of valid event types.
     - connect_timeout(int): Optional maximum amount of time to wait for connection to succeed.
    """

    def __init__(self, slacktoken, event_filters='all', connect_timeout=0):
        self._validate_filters(event_filters)

        self.ws = None

        # internal state
        self._state = STATE_INITIALIZING
        self._error = None
        self._init_ts = time.time() # connection starting timestamp

        self._config = {
          'filters': event_filters,
          'ws_url': None,
          'connect_ts': time.time(), # last connection timestamp
          'timeout': connect_timeout,
          }

        self._eventq = Queue.Queue()
        self._sendq = []

        self._webclient = WebClient(slacktoken)
        self._sdir = Directory(self._webclient)

        # trap signals for graceful shutdown
        signal.signal(signal.SIGINT, self._sig_handler)
        signal.signal(signal.SIGTERM, self._sig_handler)

        # wait for websocket connection to be established before returning
        while self._state != STATE_CONNECTED:
            self._handle_state()

    def state(self):
        """ Return a text representation of current state """
        if self._state == STATE_STOPPED:
            return 'stopped'
        if self._state == STATE_INITIALIZING:
            return 'initializing'
        if self._state == STATE_INITIALIZED:
            return 'initialized'
        if self._state == STATE_CONNECTING:
            return 'connecting'
        if self._state == STATE_CONNECTED:
            return 'connected'

    def _handle_state(self):
        log.debug(f'handling state: {self.state()}')
        try:
            self._process_state()
        except Exception as ex:
            self._error = ex
            self.close()

    def _process_state(self):
        if self._state != STATE_CONNECTED and self._timed_out():
            raise errors.TimeoutError('connection timeout exceeded')

        if self._state == STATE_INITIALIZING:
            self.team, self.user = self._webclient.login()
            self._sdir.refresh()
            self._state = STATE_INITIALIZED

        if self._state == STATE_INITIALIZED:
            try:
                ws_url = self._webclient.rtm_url()
            except errors.APIError as ex:
                raise ex
            except Exception as ex:
                log.error(ex)
                return

            self._state = STATE_CONNECTING

            self._thread = Thread(target=self._open, args=(ws_url,))
            self._thread.daemon = True
            self._thread.start()
            return

        if self._state == STATE_CONNECTING:
            time.sleep(.2)
            return

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def get_event(self, timeout=None):
        """
        return a single event object or block until an event is
        received and return it.
         - timeout(int): max time, in seconds, to block waiting for new event
        """
        # return or block until we have something to return or timeout
        return self._eventq.get(timeout=timeout)

    def events(self, idle_timeout=None):
        """
        returns a blocking generator yielding Slack event objects
        params:
         - idle_timeout(int): max time, in seconds, to wait for a new event
        """
        idle = 0 # idle time counter
        interval = .2 # poll interval
        done = False

        while not done and self._state > STATE_STOPPED:
            try:
                e = self.get_event(interval)
                idle = 0
                yield (e)
            except Queue.Empty:
                idle += interval
            except KeyboardInterrupt:
                done = True

            if idle_timeout and idle >= idle_timeout:
                log.info('idle timeout reached for events()')
                done = True
                self.close()

    def send_msg(self, text, channel, confirm=True):
        """
        Send a message to a channel or group via Slack RTM socket, returning
        the resulting message object

        params:
         - text(str): Message text to send
         - channel(Channel): Target channel
         - confirm(bool): If True, wait for a reply-to confirmation before returning.
        """

        self._send_id += 1
        msg = SlackMsg(self._send_id, channel.id, text)
        self.ws.send(msg.json)

        if confirm:
            # Wait for confirmation our message was received
            for e in self.events():
                if e.get('reply_to') == self._send_id:
                    msg.sent = True
                    msg.ts = e.ts
                    return msg
        else:
            return msg

    def lookup_user(self, match):
        """ Return User object for a given Slack ID or name """
        return self._sdir.user(match)

    def lookup_channel(self, match):
        """ Return Channel object for a given Slack ID or name """
        return self._sdir.channel(match)

    def close(self):
        self._state = STATE_STOPPED
        if self.ws:
            self.ws.on_close = lambda ws: True
            self.ws.close()
        if self._error:
            raise self._error

    #######
    # Internal Methods
    #######

    # return whether the current connection is timed out
    def _timed_out(self):
        if self._config['timeout'] == 0:
            return False
        if time.time() - self._init_ts < self._config['timeout']:
            return False
        return True

    def _sig_handler(self, signal, frame):
        log.debug("caugh signal, exiting")
        self.close()

    def _validate_filters(self, filters):
        if filters == 'all':
            filters = event_types

        if type(filters) != list:
            raise TypeError('filters must be given as a list')

        invalid = [ f for f in filters if f not in event_types ]
        if invalid:
            raise errors.ConfigError('unknown event type %s\n \
                         see https://api.slack.com/events' % filters)

    def _process_event(self, event):
        """ Extend event object with User and Channel objects """
        if event.get('user'):
            event.user = self._sdir.user(event.get('user'))

        if event.get('channel'):
            event.channel = self._sdir.channel(event.get('channel'))

        if self.user.id in event.mentions:
            event.mentions_me = True

        event.mentions = [ self._sdir.user(uid) for uid in event.mentions ]

        return event

    # return whether a given event should be omitted from emission,
    # based on configured filters
    def _filter_event(self, event):
        if self._config['filters'] == 'all':
            return False
        if event.type in self._config['filters']:
            return False
        return True

    #######
    # Websocket Handlers
    #######

    def _open(self, ws_url):
        # reset id for sending messages with each new socket
        self._send_id = 0
        self.ws = websocket.WebSocketApp(ws_url,
                                         on_message=self._event_handler,
                                         on_error=self._error_handler,
                                         on_open=self._open_handler,
                                         on_close=self._exit_handler)
        self.ws.run_forever(ping_interval=10, ping_timeout=5,
                sslopt={'cert_reqs': ssl.CERT_NONE})

    def _event_handler(self, ws, event_json):
        log.debug('event recieved: %s' % event_json)

        event = SlackEvent(json.loads(event_json))

        if self._filter_event(event):
            log.debug('ignoring filtered event: {}'.format(event.json))
            return

        self._eventq.put(self._process_event(event))

    def _open_handler(self, ws):
        log.info('websocket connection established')
        self._state = STATE_CONNECTED
        self.connect_ts = time.time()

    def _error_handler(self, ws, error):
        log.critical('websocket error:\n %s' % error)

    def _exit_handler(self, ws):
        log.warn('websocket connection closed')

        # Don't attempt reconnect if our last attempt was less than 10s ago
        if (time.time() - self.connect_ts) < 10:
            self._state = STATE_STOPPED
            self._error = errors.ConnectionError(
              'failed to establish a websocket connection'
            )
            return

        log.warn('attempting to reconnect')
        self._state = STATE_INITIALIZED
        while self._state != STATE_CONNECTED:
            self._handle_state()
