import json
import re
import time

delchars = ''.join(c for c in map(chr, range(256)) if not c.isalnum())

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
        self.event = json.loads(event_json)
        self.mentions = []

        if self.event.has_key('type'):
            self.type = self.event['type']

        if self.event.has_key('ts'):
            self.ts = self.event['ts']
        else:
            self.time = int(time.time())
        
        if self.event.has_key('text'):
            self.mentions = self._get_mentions(self.event['text'])

    def _get_mentions(self,text):
        mentions = re.findall('<@\w+>', text)
        if mentions:
            return [ str(m).translate(None,delchars) for m in mentions ]
        else:
            return []

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
