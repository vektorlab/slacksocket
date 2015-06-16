# SlackSocket Client

To instantiate a `SlackSocket` class that will setup an RTM websocket:

```python
from slacksocket import SlackSocket
s = SlackSocket('<slack-token>')
```

**Params**:

* slacktoken (str): token to authenticate with slack
* translate (bool): yield events with human-readable user/channel names rather than id. default true

**Methods**

## events

Return event object in the order received or block until an event is received and return it.

**Params**:

* event_filter (list): Slack event type(s) to filter by. Excluding a filter returns all slack events. See https://api.slack.com/events for a listing of valid event types.

**Returns** (obj): SlackEvent object

# SlackEvent

Event object received from SlackSocket

Note: If slacksocket was instantiated with translate=True(default), user and channel IDs in the event will be replaced with their human-readable versions rather than ID. 

**Attributes**:

* type (str): The Slack API event type
* time (int): UTC epoch time that the event was received by the client
* event (dict): Dictionary of the event received from slack
* json (str): Event in JSON format
