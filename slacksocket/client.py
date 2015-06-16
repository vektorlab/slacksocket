import os,json,logging,websocket,requests,time,thread
from .config import slackurl,event_types

logging.basicConfig(level=logging.WARN)
log = logging.getLogger('slacksocket')

class SlackSocketEventNameError(NameError):
    """
    Invalid name
    """
    pass

class SlackSocketAPIError(RuntimeError):
    """
    Error response from Slack API
    """
    pass

#TODO: create a common slack api request object

class SlackEvent(object):
    """
    Event received from the Slack RTM API
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
        self.event = event

class SlackClient(requests.Session):
    """
    """
    def __init__(self, token):
        super(Client, self).__init__()
        self.token = token

    def get_json(self,url):
        return self._result(self._get(url))

    def _post(self, url):
        return self.post(url, params={'token':self.token})

    def _get(self, url):
        return self.get(url, params={'token':self.token})

    def _result(self, res):
        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise errors.SlackSocketAPIError(e, res, explanation=explanation)

        rj = res.json
        if not rj['ok']:
            raise SlackSocketAPIError('Error from slack api:\n %s' % r.text)

        return rj

class SlackMsg(object):
    """
    Slack default formatted message capable of being sent via the RTM API
    params:
     - text(str)
     - channel(str)
    attributes:
     - type: Slack event type
     - time: UTC time event was received 
    """
    def __init__(self,id,text,channel):
        self.msgdict = { 'id'      : id,
                         'text'    : text,
                         'channel' : channel,
        self.time = int(time.time())
        self.json = json.dumps(event)
        self.event = event

class SlackSocket(object):
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
        self.eventq = []
        self.translate = translate
        self.client = SlackClient(slacktoken)

        self.team,self.user = self._auth_test()
        self.thread = thread.start_new_thread(self._open,())

    def events(self,event_filter='all'):
        """
        return event object in the order received or block until an event is
        received and return it.
        params:
         - event_filter(list): Slack event type(s) to filter by. Excluding a
            filter returns all slack events. See https://api.slack.com/events
            for a listing of valid event types.
        """
        #validate event filter
        if event_filter == 'all':
            event_filter = event_types

        if type(event_filter) != list:
            raise TypeError('event_filter must be given as a list')

        for f in event_filter:
            if f not in event_types:
                raise SlackSocketEventNameError('unknown event type %s\n \
                             see https://api.slack.com/events' % event_filter)

        #return or block until we have something to return
        while True:
            try:
                e = self.eventq.pop(0)
                if e.type in event_filter:
                    return e
            except IndexError:
                pass

    def send_msg(self,text):
        """
        send a message via Slack RTM socket
        """
        pass
        
    #######
    # Internal Methods
    #######

    def _open(self):
        #reset id for sending messages with each new socket
        self.send_id = 1
        ws = websocket.WebSocketApp(self._get_websocket_url(),
                                    on_message = self._event_handler,
                                    on_error   = self._error_handler,
                                    on_open    = self._open_handler,
                                    on_close   = self._exit_handler)
        ws.run_forever()

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
        
        if self.translate:
            return (test['team'],test['user'])
        else:
            return (test['team_id'],test['user_id'])

    def _lookup_user(self,user_id):
        """
        Look up a username from user id
        """
        if user_id == 'USLACKBOT':
            return "slackbot"

        members = self.client.get_json(slackurl['users'])

        for user in members:
            if user['id'] == user_id:
                return user['name']
        else:
            return "unknown"

    #TODO: add ability for lookup via id and cname
    def _lookup_channel(self,channel_id):
        """
        Look up a channelname from channel id
        """
        for channel_type in ['channels','groups','ims']:
            clist = self.client.get_json(slackurl[channel_type])[channel_type]
            for channel in clist:
                if channel['id'] == channel_id:
                    if channel_type == 'ims':
                        return { 'channel_type' : channel_type,
                                 'channel_name' : self._lookup_user(channel['user']) }
                    else:
                        return { 'channel_type' : channel_type,
                                 'channel_name' : channel['name'] }
        #if no matches were found
        return { 'channel_type' : 'unknown',
                 'channel_name' : 'unknown' }

    #######
    # Websocket Handlers
    #######

    def _event_handler(self,ws,event):
        log.debug('event recieved: %s' % event)
        event = json.loads(event)

        #TODO: make use of ctype returned from _lookup_channel
        if self.translate:
            if event.has_key('user'):
                event['user'] = self._lookup_user(event['user'])
            if event.has_key('channel'):
                c = self._lookup_channel(event['channel'])
                event['channel'] = c['channel_name']

        self.eventq.append(SlackEvent(event))

    def _open_handler(self,ws):
        log.info('websocket connection established')

    def _error_handler(self,ws,error):
        log.critical('websocket error:\n %s' % error)

    def _exit_handler(self,ws):
        self.thread = thread.start_new_thread(self.open,())
