class APIError(RuntimeError):
    """ Error response from Slack API """

class ConfigError(NameError):
    """ Invalid name """

class APINameError(NameError):
    """ Unknown or invalid name """

class ConnectionError(IOError):
    """ Unrecoverable error maintaining a websocket connection """

class TimeoutError(IOError):
    """ Timed out reaching Slack API """

class ExitError(RuntimeError):
    """ User-requested exit """
