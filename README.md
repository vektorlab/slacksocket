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

s = SlackSocket('<slack-token>',translate=True) # translate will lookup and replace user and channel IDs with their human-readable names. default true. 

for event in s.events():
    print(event.json)
```

### Sending messages
```python
from slacksocket import SlackSocket

s = SlackSocket('<slack-token>')

msg = s.send_msg('Hello there', channel_name='channel-name') 
print(msg.sent)
```

```
True
```

## Documentation

Full documentation is available on [ReadTheDocs](http://slacksocket.readthedocs.org/en/latest/client/)
