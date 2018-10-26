# Slacksocket

[![Documentation Status](https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat)](http://slacksocket.readthedocs.org/en/latest/client/) [![PyPI version](https://badge.fury.io/py/slacksocket.svg)](https://badge.fury.io/py/slacksocket)

Python interface to the Slack Real Time Messaging(RTM) API

## Install

*note*: v1.x only supports Python3 at this time is not backward compatible with earlier library versions

```bash
pip install slacksocket
```

## Usage

### Example

Example usage for a simple time bot:
```python
from datetime import datetime
from slacksocket import SlackSocket

s = SlackSocket('<slack-token>')

while True:
    event = s.get_event('message') # filter only for events of type 'message'
    if not event.mentions_me: # doesn't mention our bot, ignore
        continue
    if 'what time is it' in event.get('text'):
        text = f'@{event.user} it is currently {datetime.now()}'
        s.send_msg(text, event.channel) # respond back to origin channel

```

### Retrieving events/messages
```python
from slacksocket import SlackSocket

s = SlackSocket('<slack-token>')

# get a single event
e = s.get_event()

# get all events
for event in s.events():
    print(event.json)

# or filter events based on type 
for event in s.events('message', 'user_typing'):
    print(event.json)
```

### Sending messages
```python
from slacksocket import SlackSocket

s = SlackSocket('<slack-token>')
channel = s.lookup_channel('channel-name')

msg = s.send_msg('Hello there', channel)
print(msg.sent)
```

```
True
```

## Documentation

Full documentation is available on [ReadTheDocs](http://slacksocket.readthedocs.org/en/latest/client/)
