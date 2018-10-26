# Slacksocket

[![Documentation Status](https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat)](http://slacksocket.readthedocs.org/en/latest/client/) [![PyPI version](https://badge.fury.io/py/slacksocket.svg)](https://badge.fury.io/py/slacksocket)

Python interface to the Slack Real Time Messaging(RTM) API

## Install

```bash
pip install slacksocket
```

## Usage

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
