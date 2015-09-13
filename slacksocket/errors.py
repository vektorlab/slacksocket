class SlackSocketEventNameError(NameError):
    """ Invalid name """


class SlackSocketAPIError(RuntimeError):
    """ Error response from Slack API """


class SlackSocketConnectionError(IOError):
    """ Unrecoverable error maintaining a websocket connection """
