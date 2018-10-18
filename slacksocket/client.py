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
     - translate(bool): yield events with human-readable names
        rather than id. default true
     - event_filter(list): Optional Slack event type(s) to filter by. Excluding a
            filter returns all slack events. See https://api.slack.com/events
            for a listing of valid event types.
     - connect_timeout(int): Optional maximum amount of time to wait for connection to succeed.
    """



    def __init__(self, slacktoken, translate=True, event_filters='all', connect_timeout=0):
        if type(translate) != bool:
            raise TypeError('translate must be a boolean')
        self._validate_filters(event_filters)

        self.ws = None

        # internal state
        self._state = STATE_INITIALIZING
        self._error = None
        self._init_ts = time.time() # connection starting timestamp

        self._config = {
          'translate': translate,
          'filters': event_filters,
          'ws_url': None,
          'connect_ts': time.time(), # last connection timestamp
          'timeout': connect_timeout,
          }

        self._eventq = Queue.Queue()
        self._sendq = []

        self._webclient = WebClient(slacktoken)

        # trap signals for graceful shutdown
        signal.signal(signal.SIGINT, self._sig_handler)
        signal.signal(signal.SIGTERM, self._sig_handler)

        # wait for websocket connection to be established before returning
        while self._state != STATE_CONNECTED:
            self._handle_state()

    def user(self):
        """ Return the currently logged in user """
        return self._webclient.user

    def team(self):
        """ Return the currently logged in team """
        return self._webclient.team

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
            raise errors.SlackSocketTimeoutError('connection timeout exceeded')

        if self._state == STATE_INITIALIZING:
            self._webclient.login()
            self._state = STATE_INITIALIZED
            return

        if self._state == STATE_INITIALIZED:
            try:
                ws_url = self._webclient.rtm_url()
            except errors.SlackAPIError as ex:
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

    # return whether the current connection is timed out
    def _timed_out(self):
        if self._config['timeout'] == 0:
            return False
        if time.time() - self._init_ts < self._config['timeout']:
            return False
        return True

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

    def send_msg(self, text, channel_name=None, channel_id=None, confirm=True):
        """
        Send a message via Slack RTM socket, returning the message object
        after receiving a reply-to confirmation
        """
        if not channel_name and not channel_id:
            raise Exception('One of channel_id or channel_name \
                             parameters must be given')
        if channel_name:
            channel_id = self._webclient.name_to_id('channel', channel_name)

        self._send_id += 1
        msg = SlackMsg(self._send_id, channel_id, text)
        self.ws.send(msg.json)

        if confirm:
            # Wait for confirmation our message was received
            for e in self.events():
                if e.event.get('reply_to') == self._send_id:
                    msg.sent = True
                    msg.ts = e.ts
                    return msg
        else:
            return msg

    def get_im_channel(self, user_name):
        """
        Get a direct message channel to a particular user. Create
        one if it does not exist.
        """
        user_id = self._find_user_id(user_name)
        channel_info = self._find_channel(['ims'], 'user', user_id)

        if channel_info is None:
            channel = self._webclient.open_im_channel(user_id)

        else:
            (channel_type, matching) = channel_info
            assert channel_type == 'ims'
            assert len(matching) == 1
            channel = matching[0]

        return channel

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

    def _sig_handler(self, signal, frame):
        log.debug("caugh signal, exiting")
        self.close()

    def _validate_filters(self, filters):
        if filters == 'all':
            filters = event_types

        if type(filters) != list:
            raise TypeError('filters must be given as a list')

        for f in filters:
            if f not in event_types:
                raise errors.SlackSocketEventNameError('unknown event type %s\n \
                             see https://api.slack.com/events' % filters)


    def _translate_event(self, event):
        """
        Translate all user and channel ids in an event to human-readable names
        """
        if 'user' in event.event:
            event.event['user'] = self._webclient.id_to_name('user', event.event['user'])

        if 'channel' in event.event:
            chan = event.event['channel']
            if isinstance(chan, dict):
                # if channel is newly created, a channel object is returned from api
                # instead of a channel id
                event.event['channel'] = chan['name']
            else:
                event.event['channel'] = self._webclient.id_to_name('channel', chan)

        event.mentions = [ self._webclient.id_to_name(uid) for uid in event.mentions]

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
            log.debug('ignoring filtered event: {}'.format(event.event))
            return

        if self._config['translate']:
            event = self._translate_event(event)

        self._eventq.put(event)

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
            self._error = errors.SlackSocketConnectionError(
              'failed to establish a websocket connection'
            )
            return

        log.warn('attempting to reconnect')
        self._state = STATE_INITIALIZED
        while self._state != STATE_CONNECTED:
            self._handle_state()
