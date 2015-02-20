# Slacksocket

Slacksocket is a Python interface to the Slack Real Time Messaging(RTM) API

# Examples

```python
from slacksocket import SlackSocket

s = SlackSocket('<slack-token>',translate=True) # translate will lookup and replace user and channel IDs with their human-readable names. default true. 

while True:
    event = s.get_event()
    print(event.json)
```
