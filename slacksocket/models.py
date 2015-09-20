import json
import re
import time

translate_map = {ord(c): None for c in map(chr, list(range(256))) if not c.isalnum()}


class SlackEvent(object):
    """
    Event received from the Slack RTM API
    params:
     - event_json(json string)
     - event_obj(json object)
    attributes:
     - type(type): Slack event type
     - ts(float): UTC event timestamp
    """

    def __init__(self, event_json, event_obj):
        self.json = event_json
        self.event = event_obj
        self.mentions = []

        if 'type' in self.event:
            self.type = self.event['type']

        if 'ts' in self.event:
            self.ts = self.event['ts']
        else:
            self.ts = int(time.time())

        if 'text' in self.event:
            self.mentions = self._get_mentions(self.event['text'])

    def _get_mentions(self, text):
        mentions = re.findall('<@\w+>', text)
        if mentions:
            return [str(m).translate(translate_map) for m in mentions]
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

    def __init__(self, id, channel, text):
        self.sent = False
        self.payload = {'id': id,
                        'type': 'message',
                        'text': text,
                        'channel': channel}
        self.json = json.dumps(self.payload)
