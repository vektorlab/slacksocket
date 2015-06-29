# Slacksocket

[![Documentation Status](https://readthedocs.org/projects/slacksocket/badge/?version=latest)](https://readthedocs.org/projects/slacksocket/?badge=latest)

Slacksocket is a Python interface to the Slack Real Time Messaging(RTM) API

# Install

```bash
pip install slacksocket
```

# Usage

## Retrieving events/messages
```python
from slacksocket import SlackSocket

s = SlackSocket('<slack-token>',translate=True) # translate will lookup and replace user and channel IDs with their human-readable names. default true. 

for event = s.events():
    print(event.json)
```

## Sending messages
```python
from slacksocket import SlackSocket

s = SlackSocket('<slack-token>')

msg = s.send_msg('Hello there', 'channel-name') 
print(msg.sent)
```

```
True
```

# Documentation

Full documentation is available in the docs/ folder or at http://slacksocket.readthedocs.org/en/latest/
