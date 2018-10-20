import re
import sys
import json
from time import time

translate_map = { ord(c): None for c in map(chr, list(range(256))) if not c.isalnum() }


class SlackEvent(dict):
    """
    Event received from the Slack RTM API
    params:
     - event_obj(dict)
    attributes:
     - type(str): Slack event type
     - user(str): Slack user ID (or name if translated), if applicable. default None.
     - channel(str): Slack channel ID (or name if translated), if applicable. default None.
     - ts(float): UTC event timestamp
     - metions(list): List of Slack user IDs (or names if translated) mentioned in event text
    """

    def __init__(self, event_obj):
        super(SlackEvent, self).__init__()
        self.update(event_obj)
        self.mentions = []

        self.type = self.get('type')
        self.ts = self.get('ts', int(time()))
        self.mentions = self._mentions(self.get('text', ''))

        self.user = self.get('user')
        self.channel = self.get('channel')

        if isinstance(self.channel, dict):
            # if channel is newly created, a channel object is returned from api
            # instead of a channel id
            self.channel = self.channel.get('id')

    @property
    def json(self):
        return json.dumps(self)

    def _mentions(self, text):
        mentions = re.findall('<@\w+>', text)

        if mentions and sys.version_info.major == 2:
            return [ unicode(m).translate(translate_map) for m in mentions ]

        if mentions and sys.version_info.major == 3:
            return [ str(m).translate(translate_map) for m in mentions ]

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
