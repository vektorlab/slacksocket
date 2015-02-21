import os,json,logging,websocket,requests,time,thread

logging.basicConfig(level=logging.WARN)
log = logging.getLogger('slacksocket')

slackurl = { 'rtm'   : 'https://slack.com/api/rtm.start',
             'users' : 'https://slack.com/api/users.list' }

class SlackEvent(object):
    """
    SlackEvent is an event received from the Slack RTM API
    params:
     - event(dict)
    attributes:
     - type: Slack event type
     - time: UTC time event was received 
    """
    def __init__(self,event):
        self.type = event['type']
        self.time = int(time.time())
        self.json = json.dumps(event)

class SlackSocket(object):
    #TODO: add method to properly exit, close socket
    """
    SlackSocket class provides a streaming interface to the Slack Real Time
    Messaging API
    params:
     - slacktoken(str): token to authenticate with slack
     - translate(bool): yield events with human-readable names
        rather than id. default true
    """
    def __init__(self,slacktoken,translate=True):
        if type(translate) != bool:
            raise TypeError('translate must be a boolean')
        self.events = []
        self.token = slacktoken
        self.translate = translate
        self.thread = thread.start_new_thread(self.start,())

    def start(self):
        ws = websocket.WebSocketApp(self._get_websocket_url(),
                                    on_message = self._event_handler,
                                    on_error   = self._error_handler,
                                    on_open    = self._open_handler,
                                    on_close   = self._exit_handler)
        ws.run_forever()

    def get_event(self):
        #TODO: add ability to filter by event type
        while True:
            try:
                return self.events.pop(0)
            except IndexError:
                pass

    def _get_websocket_url(self):
        """
        retrieve a fresh websocket url from slack api
        """
        r = requests.get(slackurl['rtm'],params={'token':self.token})
        rj = r.json()
        if not rj['ok']:
            raise RuntimeError('Error from slack api:\n %s' % r.text)

        return rj['url']

    def _lookup_user(self,user_id):
        """
        Look up a username from user id
        """
        if user_id == 'USLACKBOT':
            return "slackbot"

        r = requests.get(slackurl['users'],params={'token':self.token})
        rj = r.json()
        if not rj['ok']:
            log.critical('error from slack api:\n %s' % r)

        for user in rj['members']:
            if user['id'] == user_id:
                return user['name']
        else:
            return "unknown"

    #######
    # Handlers
    #######

    def _event_handler(self,ws,event):
        log.debug('event recieved: %s' % event)
        event = json.loads(event)

        if self.translate:
            if event.has_key('user'):
                event['user'] = self._lookup_user(event['user'])
            #TODO: add channel id lookup

        self.events.append(SlackEvent(event))

    def _open_handler(self,ws):
        log.info('websocket connection established')

    def _error_handler(self,ws,error):
        log.critical('websocket error:\n %s' % error)

    def _exit_handler(ws):
        #TODO: attempt websocket reconnection
        raise Exception('websocket closed!')
