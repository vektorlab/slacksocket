import ssl
import json
import time
import signal
import logging
import websocket
from threading import Thread

import slacksocket.errors as errors
from .config import event_types
from .models import SlackEvent, SlackMsg
from .webclient import WebClient

try:
    import queue as Queue # python3
except ImportError:
    import Queue # python2

log = logging.getLogger('slacksocket')

STATE_STOPPED = 0
STATE_INITIALIZED = 1
STATE_CONNECTING = 2
STATE_CONNECTED = 3
STATE_UNCHANGED = 4

class SlackSocket(object):
    """
    SlackSocket class provides a streaming interface to the Slack Real Time
    Messaging API
    params:
     - slacktoken(str): token to authenticate with slack
     - connect_timeout(int): Optional maximum amount of time to wait for connection to succeed.
    """

    def __init__(self, slacktoken, connect_timeout=0):
        self.ws = None

        # internal state
        self._internalq = Queue.Queue() # internal event queue
        self._state = None
        self._error = None

        # stats tracking
        self._stats = {
          'events_recieved': 0,
          'events_dropped': 0,
          'messages_sent': 0,
          'connected_since': 0
        }

        self.timeout = connect_timeout

        self._eventq = Queue.Queue()
        self._sendq = []

        self._slack = WebClient(slacktoken, self.timeout)
        self.team, self.user = self._slack.login()

        # trap signals for graceful shutdown
        signal.signal(signal.SIGINT, self._sig_handler)
        signal.signal(signal.SIGTERM, self._sig_handler)

        self._thread = Thread(target=self._run)
        self._thread.start()

        self._set_state(STATE_INITIALIZED)
        # wait for websocket connection to be established before returning
        while self._state not in (STATE_STOPPED, STATE_CONNECTED):
            time.sleep(.2)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def stats(self):
        """
        Return a dictionary of SlackSocket stats, including the number
        of messages sent and recieved
        """
        return self._stats

    def get_event(self, *etypes, timeout=None):
        """
        Return a single event object or block until an event is
        received and return it.
         - etypes(str): If defined, Slack event type(s) not matching
           the filter will be ignored. See https://api.slack.com/events for
           a listing of valid event types.
         - timeout(int): Max time, in seconds, to block waiting for new event
        """
        self._validate_etypes(*etypes)
        start = time.time()
        e = self._eventq.get(timeout=timeout)

        if isinstance(e, Exception):
            raise e

        self._stats['events_recieved'] += 1
        if etypes and e.type not in etypes:
            if timeout:
                timeout -= time.time() - start
            log.debug('ignoring filtered event: {}'.format(e.json))
            self._stats['events_dropped'] += 1
            return self.get_event(*etypes, timeout=timeout)

        return e

    def events(self, *etypes, idle_timeout=None):
        """
        returns a blocking generator yielding Slack event objects
        params:
         - etypes(str): If defined, Slack event type(s) not matching
           the filter will be ignored. See https://api.slack.com/events for
           a listing of valid event types.
         - idle_timeout(int): optional maximum amount of time (in seconds)
           to wait between events before returning
        """

        while self._state != STATE_STOPPED:
            try:
                yield self.get_event(*etypes, timeout=idle_timeout)
            except Queue.Empty:
                log.info('idle timeout reached for events()')
                return

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
        self._stats['messages_sent'] += 1

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
        return self._slack.user(match)

    def lookup_channel(self, match):
        """ Return Channel object for a given Slack ID or name """
        return self._slack.channel(match)

    def close(self):
        self._set_state(STATE_STOPPED)
        self._thread.join()

    #######
    # Internal Methods
    #######

    def _set_state(self, state):
        """ notify manager thread of state change """
        self._internalq.put(state)

    def _sig_handler(self, signal, frame):
        log.debug("caugh signal, exiting")
        self.close()

    def _process_event(self, event):
        """ Extend event object with User and Channel objects """
        if event.get('user'):
            event.user = self.lookup_user(event.get('user'))

        if event.get('channel'):
            event.channel = self.lookup_channel(event.get('channel'))

        if self.user.id in event.mentions:
            event.mentions_me = True

        event.mentions = [ self.lookup_user(uid) for uid in event.mentions ]

        return event

    @staticmethod
    def _validate_etypes(*etypes):
        if not etypes:
            return

        invalid = [ f for f in etypes if f not in event_types ]
        if invalid:
            raise errors.ConfigError('unknown event type %s\n \
                         see https://api.slack.com/events' % invalid)

    #######
    # Websocket Handlers
    #######

    def _run(self):
        conn_start = None

        while True:
            # wait for notification of state change
            state = self._internalq.get()
            if state != STATE_UNCHANGED:
                self._state = state

            if self._state == STATE_STOPPED:
                if self.ws:
                    self.ws.close()

                # break any running event loops
                if self._error:
                    self._eventq.put(self._error)
                    raise self._error
                else:
                    self._eventq.put(errors.ExitError('stopped'))
                break

            if self._state == STATE_INITIALIZED:
                if not conn_start:
                    conn_start = time.time()
                self._wsthread = Thread(target=self._open)
                self._wsthread.daemon = True
                self._wsthread.start()

            if self._state == STATE_CONNECTING:
                if self.timeout and time.time() - conn_start >= self.timeout:
                    self._error = errors.TimeoutError('connection timeout exceeded')
                    self.close()
                log.info('establishing websocket connection')
                time.sleep(.5)
                self._set_state(STATE_UNCHANGED)

            if self._state == STATE_CONNECTED:
                log.info('websocket connection established')
                conn_start = None
                self._stats['connected_since'] = time.time()

        log.debug('worker stopped')

    def _open(self):
        self._send_id = 0 # reset id for sending messages with each new socket
        self._set_state(STATE_CONNECTING)

        try:
            ws_url = self._slack.rtm_url()
        except Exception as ex:
            self._error = ex
            self.close()

        self.ws = websocket.WebSocketApp(ws_url,
                                         keep_running=False,
                                         on_message=self._event_handler,
                                         on_error=self._error_handler,
                                         on_open=self._open_handler,
                                         on_close=self._exit_handler)
        self.ws.run_forever(ping_interval=10, ping_timeout=5,
                sslopt={'cert_reqs': ssl.CERT_NONE})
        self._set_state(STATE_INITIALIZED)

    def _event_handler(self, ws, event_json):
        log.debug('event recieved: %s' % event_json)
        event = SlackEvent(json.loads(event_json))
        self._eventq.put(self._process_event(event))

    def _open_handler(self, ws):
        self._set_state(STATE_CONNECTED)

    def _error_handler(self, ws, error):
        log.critical('websocket error:\n %s' % error)

    def _exit_handler(self, ws):
        log.warn('websocket connection closed')
