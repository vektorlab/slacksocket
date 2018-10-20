import re
import sys
import json
from time import time

mentions_re = re.compile('<@(\w+)>')

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
     - mentions_me(bool): Whether this message @mentions the logged in bot/user
    """

    def __init__(self, event_obj):
        super(SlackEvent, self).__init__()
        self.update(event_obj)

        self.type = self.get('type')
        self.ts = self.get('ts', int(time()))

        self.mentions = mentions_re.findall(self.get('text', ''))
        self.mentions_me = False

        self.user = self.get('user')
        self.channel = self.get('channel')

        if isinstance(self.channel, dict):
            # if channel is newly created, a channel object is returned from api
            # instead of a channel id
            self.channel = self.channel.get('id')

    @property
    def json(self):
        return json.dumps(self)


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
