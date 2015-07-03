import json
import re
import time

class SlackEvent(object):
    """
    Event received from the Slack RTM API
    params:
     - event_json(json)
    attributes:
     - type(type): Slack event type
     - ts(float): UTC event timestamp
    """
    def __init__(self,event_json):
        self.json = event_json
        self.event = json.loads(self.event_json)
        self.mentions = None

        if event.has_key('type'):
            self.type = event['type']

        if event.has_key('ts'):
            self.ts = event['ts']
        else:
            self.time = int(time.time())
        
        if event.has_key('text'):
            self.mentions = self._get_mentions(self.event['text'])

    def _get_mentions(self,text):
        mentions = re.findall('<@\w+>:', text)
        if mentions:
            return [ m.translate(None,'<@>:') for m in mentions ]
        else:
            return None

class SlackMsg(object):
    """
    Slack default formatted message capable of being sent via the RTM API
    params:
     - text(str)
     - channel(str)
    attributes:
     - type: Slack event type
     - ts: UTC time event was received 
    """
    def __init__(self,id,channel,text):
        self.sent = False
        self.payload = { 'id'      : id,
                         'type'    : 'message',
                         'text'    : text,
                         'channel' : channel }
        self.json = json.dumps(self.payload)
