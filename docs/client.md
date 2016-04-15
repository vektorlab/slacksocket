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
    s.send_msg(text='hello', channel_name='general')
```

**Params**:

* slacktoken (str): token to authenticate with slack
* translate (bool): yield events with human-readable user/channel names rather than id. default True
* event_filter (list): Slack event type(s) to filter by. Excluding a filter returns all slack events. See https://api.slack.com/events for a listing of valid event types.

**Methods**

## get_event

Return a single event object in the order received or block until an event is received and return it.

**Returns** (obj): SlackEvent object

## events

Return a generator yielding SlackEvent objects

**Returns** (generator): A generator of SlackEvent objects

## send_msg

Send a message via Slack RTM socket and wait for confirmation it was received. One of either channel_name or channel_id params is required.

**Params**:

* text (str): Message body to send
* channel_name(str): Name of the channel to post message
* channel_id(str): Slack ID of the channel to post message
* confirm(bool): Boolean to toggle blocking until a reply back is received from slack. default True 

**Returns** (obj): SlackMsg object

## get_im_channel

Get a direct message channel for a user. Open one if it does not already exist.

**Params**:

* username (str): Display name of the user to message

**Returns** (dict): dictionary with the channel information

**Example**
```python
s = SlackSocket(<token>)
s.get_im_channel('my_user')
{'is_user_deleted': False, 'id': 'D0L7XNQCV', 'is_im': True, 'user': 'U071Y0CSZ', 'created': 1454542620}
```

# SlackEvent

Event object received from SlackSocket

Note: If slacksocket was instantiated with translate=True(default), user and channel IDs in the event will be replaced with their human-readable versions rather than ID. 

**Attributes**:

* type (str): The Slack API event type
* time (int): UTC epoch time that the event was received by the client
* event (dict): Dictionary of the event received from slack
* json (str): Event encoded as JSON

# SlackMsg

Msg created and sent via Slack RTM websocket

**Attributes**:

* time (int): UTC epoch time that the message was acknowledged as sent
* sent (bool): Boolean for message being sent successfully
* json (str): Message in JSON format
