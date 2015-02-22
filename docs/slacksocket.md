# SlackSocket

To instantiate a `SlackSocket` class that will setup an RTM websocket:

```python
from slacksocket import SlackSocket
s = SlackSocket('<slack-token>')
```

**Params**:

* slacktoken (str): token to authenticate with slack
* translate (bool): yield events with human-readable user/channel names rather than id. default true

****

## get_event

Return event object in the order received or block until an event is received and return it.

**Returns** (obj): SlackEvent object
