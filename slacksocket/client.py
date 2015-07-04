import os
import json
import logging
import websocket
import requests
import time
import thread
import slacksocket.errors as errors
from .config import slackurl,event_types
from .models import SlackEvent,SlackMsg

log = logging.getLogger('slacksocket')

class SlackClient(requests.Session):
    """
    """
    def __init__(self,token):
        super(SlackClient, self).__init__()
        self.token = token

    def get_json(self,url):
        return self._result(self._get(url))

    def _post(self,url,payload=None):
        if payload:
            return self.post(url,params={'token':self.token},payload=payload)
        return self.post(url,params={'token':self.token})

    def _get(self,url):
        return self.get(url,params={'token':self.token})

    def _result(self,res):
        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise errors.SlackSocketAPIError(e)

        rj = res.json()
        if not rj['ok']:
            raise errors.SlackSocketAPIError('Error from slack api:\n %s' % r.text)

        return rj

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
        self.sendq = []
        self.translate = translate
        self.client = SlackClient(slacktoken)

        self.team,self.user = self._auth_test()
        self.thread = thread.start_new_thread(self._open,())

    def get_event(self,event_filter='all'):
        """
        return a single event object or block until an event is
        received and return it.
        params:
         - event_filter(list): Slack event type(s) to filter by. Excluding a
            filter returns all slack events. See https://api.slack.com/events
            for a listing of valid event types.
        """
        self._validate_filters(event_filter)

        #return or block until we have something to return
        while True:
            try:
                e = self.eventq.pop(0)
                #return immediately if no filtering
                if event_filter == 'all': 
                    return e
                if e.type in event_filter:
                    return e
            except IndexError:
                time.sleep(.2)

    def events(self,event_filter='all'):
        """
        returns a blocking generator yielding Slack event objects
        params:
         - event_filter(list): Slack event type(s) to filter by. Excluding a
            filter returns all slack events. See https://api.slack.com/events
            for a listing of valid event types.
        """
        self._validate_filters(event_filter)

        while True:
            e = self.get_event(event_filter=event_filter)
            yield(e)

    def send_msg(self,text,channel_name=None,channel_id=None):
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

        self.send_id += 1
        msg = SlackMsg(self.send_id,channel_id,text)
        self.ws.send(msg.json)
        for e in self.events():
            if e.event.has_key('reply_to'):
                if e.event['reply_to'] == self.send_id:
                    msg.sent = True
                    msg.ts = e.event['ts']
                    return msg
        return msg
        
    #######
    # Internal Methods
    #######

    def _open(self):
        #reset id for sending messages with each new socket
        self.send_id = 0
        self.ws = websocket.WebSocketApp(self._get_websocket_url(),
                                    on_message = self._event_handler,
                                    on_error   = self._error_handler,
                                    on_open    = self._open_handler,
                                    on_close   = self._exit_handler)
        self.ws.run_forever()

    def _validate_filters(self,filters):
        if filters == 'all':
            filters = event_types

        if type(filters) != list:
            raise TypeError('filters must be given as a list')

        for f in filters:
            if f not in event_types:
                raise SlackSocketEventNameError('unknown event type %s\n \
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

        members = self.client.get_json(slackurl['users'])['members']

        for user in members:
            if user['id'] == user_id:
                return user['name']
        else:
            return "unknown"

    def _lookup_channel_by_id(self,id):
        """
        Look up a channelname from channel id
        params:
         - id(str): The channel id to lookup
        """
        for ctype in ['channels','groups','ims']:
            channel_list = self.client.get_json(slackurl[ctype])[ctype]
            matching = [ c for c in channel_list if c['id'] == id ]
            if matching:
                channel = matching[0]
                if ctype == 'ims':
                    cname = self._lookup_user(channel['user'])
                else:
                    cname = channel['name']

                return { 'channel_type' : ctype,
                         'channel_name' : cname }

        #if no matches were found
        return { 'channel_type' : 'unknown',
                 'channel_name' : 'unknown' }

    def _lookup_channel_by_name(self,cname):
        """
        Look up a channel id from a given name
        params:
         - cname(str): The channel name to lookup
        """
        for ctype in ['channels','groups']:
            channel_list = self.client.get_json(slackurl[ctype])[ctype]
            matching = [ c for c in channel_list if c['name'] == cname ]
            if matching:
                channel = matching[0]

                return { 'channel_type' : ctype,
                         'channel_id'   : channel['id'] }

        #if no matches were found
        return { 'channel_type' : 'unknown',
                 'channel_id'   : 'unknown' }

    def _translate_event(self,event):
        """
        Translate all user and channel ids in an event to human-readable names
        """
        if event.event.has_key('user'):
            event.event['user'] = self._lookup_user(event.event['user'])

        if event.event.has_key('channel'):
            c = self._lookup_channel_by_id(event.event['channel'])
            event.event['channel'] = c['channel_name']

        event.mentions = [ self._lookup_user(u) for u in event.mentions ]

        return event
        
    #######
    # Websocket Handlers
    #######

    def _event_handler(self,ws,event_json):
        log.debug('event recieved: %s' % event_json)
        event = SlackEvent(event_json)

        #TODO: make use of ctype returned from _lookup_channel
        if self.translate:
            event = self._translate_event(event)

        self.eventq.append(event)

    def _open_handler(self,ws):
        log.info('websocket connection established')
        self.connect_ts = time.time()

    def _error_handler(self,ws,error):
        log.critical('websocket error:\n %s' % error)

    def _exit_handler(self,ws):
        log.warn('websocket connection closed')
        # Don't attempt reconnect if our last attempt was less than 10s ago
        if (time.time() - self.connect_ts) < 10:
            raise errors.SlackSocketConnectionError(
                    'Failed to establish a websocket connection'
                    )
        log.warn('attempting to reconnect')
        self.thread = thread.start_new_thread(self._open,())
