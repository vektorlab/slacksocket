# SlackSocket Client

To instantiate a SlackSocket object that will setup an RTM websocket:

```python
from slacksocket import SlackSocket
s = SlackSocket('<slack-token>')
```

Likewise, SlackSocket can be used as a context:
```python
from slacksocket import SlackSocket
with SlackSocket('<slack-token>') as s:
    s.send_msg(text='hello', s.lookup_channel('general'))
```

**Params**:

* slacktoken (str): token to authenticate with slack
* translate (bool): yield events with human-readable user/channel names rather than id. default True
* event_filter (list): Slack event type(s) to filter by. Excluding a filter returns all slack events. See https://api.slack.com/events for a listing of valid event types.

**Methods**

## get_event

Return a single event object in the order received or block until an event is received and return it.

**Params**:

* etypes(str): If defined, Slack event type(s) not matching the filter will be ignored. See https://api.slack.com/events for a listing of valid event types. 
* timeout(int): optional max time in seconds to block waiting for new event

**Returns** (obj): SlackEvent object

## events

Return a generator yielding SlackEvent objects

**Params**:

* etypes(str): If defined, Slack event type(s) not matching the filter will be ignored. See https://api.slack.com/events for a listing of valid event types. 
* idle_timeout(int): optional max time in seconds to wait for new events

**Returns** (generator): A generator of SlackEvent objects

## send_msg

Send a message via Slack RTM socket and wait for confirmation it was received. One of either channel_name or channel_id params is required.

**Params**:

* text (str): Message body to send
* channel(slacksocket.models.Channel): Channel to post message
* confirm(bool): Boolean to toggle blocking until a reply back is received from slack. default True 

**Returns** (obj): SlackMsg object

## lookup_user

Lookup a Slack user by ID or name

**Params**:

* match(str): Slack ID or display name

**Returns** (slacksocket.models.User): Matching User object

## lookup_channel

Lookup a Slack channel by ID or name

**Params**:

* match(str): Slack ID or display name

**Returns** (slacksocket.models.Channel): Matching Channel object

# SlackEvent

Event object received from SlackSocket

Note: If slacksocket was instantiated with translate=True(default), user and channel IDs in the event will be replaced with their human-readable versions rather than ID. 

**Attributes**:

* ts (int): UTC epoch time that the event was received by the client
* type (str): The Slack API event type
* user (slacksocket.models.User): Slack User object, if applicable
* channel (slacksocket.models.Channel): Slack Channel object, if applicable
* mentions(list): List of any Slack User objects mentioned in the event text
* mentions_me(bool): Whether the event mentions the currently logged in user/bot
* json (str): Event encoded as JSON

# SlackMsg

Msg created and sent via Slack RTM websocket

**Attributes**:

* time (int): UTC epoch time that the message was acknowledged as sent
* sent (bool): Boolean for message being sent successfully
* json (str): Message in JSON format

# User

Object representing a Slack User

**Attributes**:

* id (str): Users Slack ID
* name (str): Users display name

# Channel

Object representing a Slack channel, group, or im

**Attributes**:

* id (str): Channel Slack ID
* name (str): Channel display name
