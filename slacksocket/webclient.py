import logging
import requests
from threading import Lock

import slacksocket.errors as errors
from .config import urls

log = logging.getLogger('slacksocket')

class WebClient(requests.Session):
    """
    Minimal client for connecting to Slack web API and translating user/channel
    IDs to human-readable names
    """

    def __init__(self, token):
        self._token = token
        super(WebClient, self).__init__()

    def login(self):
        """ perform API auth test returning user and team name """
        test = self._get(urls['test'])
        return test['team'], test['user']

    def rtm_url(self):
        """ Retrieve a fresh websocket url from slack api """
        return self._get(urls['rtm'])['url']

    def open_im(self, user_id):
        res = self._post(urls['im.open'], user=user_id)
        return res['channel']

    def _get(self, url, **params):
        return self._do(url, **params)

    def _post(self, url, **params):
        return self._do(url, method='POST', **params)

    def _do(self, url, method='GET', max_attempts=3, **params):
        if max_attempts <= 0:
            raise errors.APIError('max retries exceeded')

        params['token'] = self._token
        res = self.request(method, url, params=params, timeout=5)

        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise errors.APIError(e)

        rj = res.json()

        if rj['ok']:
            return rj

        # process error
        if rj['error'] == 'migration_in_progress':
            log.info('socket in migration state, retrying')
            time.sleep(2)
            return self.get(url, method, max_attempts-1, **params)
        else:
            raise errors.APIError('Error from slack api:\n%s' % res.text)

    def _get_pages(self, url, **params):
        params['cursor'] = ''

        while True:
            res = self._get(url, **params)
            if 'response_metadata' in res:
                params['cursor'] = res['response_metadata'].get('next_cursor')
            yield res
            if not params['cursor']:
                return
