import re
import sys
import json
from time import time

mentions_re = re.compile('<@(\w+)>')

class DirItem(dict):
    """
    Generic Slack directory item
    attributes:
     - id(str): Slack ID
     - name(str): Slack human-readable name
    """
    def __init__(self, data):
        super(DirItem, self).__init__(data)
        self.id = self.get('id', 'unknown')
        self.name = self.get('name', 'unknown')

    def __str__(self):
        return self.name

class User(DirItem):
    def __repr__(self):
        return f'User({self.name} <{self.id}>)'

class Channel(DirItem):
    def __repr__(self):
        return f'Channel({self.name} <{self.id}>)'

class SlackEvent(dict):
    """
    Event received from the Slack RTM API
    params:
     - data(dict)
    attributes:
     - type(str): Slack event type
     - user(User): Slack User object, if applicable. default None.
     - channel(Channel): Slack Channel object, if applicable. default None.
     - ts(float): UTC event timestamp
     - metions(list): List of Slack User objects mentioned in event text
     - mentions_me(bool): Whether this message @mentions the logged in bot/user
    """

    def __init__(self, data):
        super(SlackEvent, self).__init__(data)

        self.type = self.get('type')
        self.ts = self.get('ts', int(time()))

        self.mentions = mentions_re.findall(self.get('text', ''))
        self.mentions_me = False

        self.user = None
        self.channel = None

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
