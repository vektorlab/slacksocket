import os,json,logging,websocket,requests,time,thread

logging.basicConfig(level=logging.WARN)
log = logging.getLogger('slacksocket')

slackurl = { 'rtm'   : 'https://slack.com/api/rtm.start',
             'users' : 'https://slack.com/api/users.list' }

#TODO: add event_type groups for all channel events, all group events, etc.
event_types = [ 'hello',
        'message',
        'channel_marked',
        'channel_created',
        'channel_joined',
        'channel_left',
        'channel_deleted',
        'channel_rename',
        'channel_archive',
        'channel_unarchive',
        'channel_history_changed',
        'im_created',
        'im_open',
        'im_close',
        'im_marked',
        'im_history_changed',
        'group_joined',
        'group_left',
        'group_open',
        'group_close',
        'group_archive',
        'group_unarchive',
        'group_rename',
        'group_marked',
        'group_history_changed',
        'file_created',
        'file_shared',
        'file_unshared',
        'file_public',
        'file_private',
        'file_change',
        'file_deleted',
        'file_comment_added',
        'file_comment_edited',
        'file_comment_deleted',
        'presence_change',
        'manual_presence_change',
        'pref_change',
        'user_change',
        'team_join',
        'star_added',
        'star_removed',
        'emoji_changed',
        'commands_changed',
        'team_pref_change',
        'team_rename',
        'team_domain_change',
        'email_domain_changed',
        'bot_added',
        'bot_changed',
        'accounts_changed',
        'team_migration_started' ]

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
        self.events = []
        self.token = slacktoken
        self.translate = translate
        self.thread = thread.start_new_thread(self.open,())

    def open(self):
        ws = websocket.WebSocketApp(self._get_websocket_url(),
                                    on_message = self._event_handler,
                                    on_error   = self._error_handler,
                                    on_open    = self._open_handler,
                                    on_close   = self._exit_handler)
        ws.run_forever()

    def get_event(self,type='all'):
        """
        return event object in the order received or block until an event is
        received and return it.
        params:
         - type(str): A slack event type to filter by. Default 'all' returns
            all slack events. See https://api.slack.com/events for a listing
            of valid event types.
        """
        if type != 'all':
            if type not in event_types:
                raise SlackSocketEventNameError('unknown event type %s\n \
                                see https://api.slack.com/events' % type)
        while True:
            try:
                if type == 'all':
                    return self.events.pop(0)
                else:
                    e = self.events.pop(0)
                    if e.type == type:
                        return e
            except IndexError:
                pass

    def _get_websocket_url(self):
        """
        retrieve a fresh websocket url from slack api
        """
        r = requests.get(slackurl['rtm'],params={'token':self.token})
        rj = r.json()
        if not rj['ok']:
            raise SlackSocketAPIError('Error from slack api:\n %s' % r.text)

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

    def _exit_handler(self,ws):
        self.thread = thread.start_new_thread(self.open,())
