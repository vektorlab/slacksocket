class SlackAPIError(RuntimeError):
    """ Error response from Slack API """

class SlackSocketEventNameError(NameError):
    """ Invalid name """

class SlackSocketConnectionError(IOError):
    """ Unrecoverable error maintaining a websocket connection """