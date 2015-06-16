# Slacksocket

[![Documentation Status](https://readthedocs.org/projects/slacksocket/badge/?version=latest)](https://readthedocs.org/projects/slacksocket/?badge=latest)

Slacksocket is a Python interface to the Slack Real Time Messaging(RTM) API

# Install

```bash
pip install slacksocket
```

# Usage

```python
from slacksocket import SlackSocket

s = SlackSocket('<slack-token>',translate=True) # translate will lookup and replace user and channel IDs with their human-readable names. default true. 

while True:
    event = s.events()
    print(event.json)
```

```
{"type": "hello"}
{"text": "ah", "ts": "1424419060.000268", "user": "bradley", "reply_to": 31, "type": "message", "channel": "D03ABT9"}
```

# Documentation

Full documentation is available in the docs/ folder or at http://slacksocket.readthedocs.org/en/latest/
