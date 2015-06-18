class SlackSocketEventNameError(NameError):
    """
    Invalid name
    """
    pass

class SlackSocketAPIError(RuntimeError):
    """
    Error response from Slack API
    """
    pass

