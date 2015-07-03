import json
import time

class SlackEvent(object):
    """
    Event received from the Slack RTM API
    params:
     - event(dict)
    attributes:
     - type: Slack event type
     - ts: UTC time event was received 
    """
    def __init__(self,event):
        if event.has_key('type'):
            self.type = event['type']
        self.ts = int(time.time())
        self.json = json.dumps(event)
        self.event = event

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
