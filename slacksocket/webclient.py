import logging
import requests
import slacksocket.errors as errors

log = logging.getLogger('slacksocket')

class WebClient(requests.Session):
    """ Minimal client for connecting to Slack web API """

    def __init__(self, token):
        self._token = token
        super(WebClient, self).__init__()

    def get(self, url, method='GET', max_attempts=3, **params):
        if max_attempts == 0:
            raise errors.SlackAPIError('Max retries exceeded')
        elif max_attempts < 0:
            message = 'Expected max_attempts >= 0, got {0}'\
                .format(max_attempts)
            raise ValueError(message)

        params['token'] = self._token
        res = self.request(method, url, params=params)

        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise errors.SlackAPIError(e)

        rj = res.json()

        if rj['ok']:
            return rj

        # process error
        if rj['error'] == 'migration_in_progress':
            log.info('socket in migration state, retrying')
            time.sleep(2)
            return self.get(url,
                            method=method,
                            max_attempts=max_attempts - 1,
                            **params)
        else:
            raise errors.SlackAPIError('Error from slack api:\n%s' % res.text)
