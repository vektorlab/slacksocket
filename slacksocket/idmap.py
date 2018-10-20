from threading import Lock

from .config import urls

def cached(fn):
    """ decorator to provide cache refreshing on failed lookups """
    def wrap(obj, *args):
        res = fn(obj, *args)
        if res == 'unknown':
            # reload cache and try again
            obj.refresh()
            res = fn(obj, *args)
        return res
    return wrap

class IDMap(object):
    def __init__(self, webclient):
        self._wc = webclient
        self._users = Cache()
        self._channels = Cache()

    def refresh(self):
        self._users.update(self._user_gen)
        self._channels.update(self._channel_gen)

    @cached
    def user_name(self, sid):
        """ return user name from id """
        return self._users.id_to_name(sid)

    @cached
    def user_id(self, name):
        """ return user id from name """
        return self._users.name_to_id(name)

    @cached
    def channel_name(self, sid):
        """ return channel name from id """
        return self._channels.id_to_name(sid)

    @cached
    def channel_id(self, name):
        """ return channel id from name """
        return self._channels.name_to_id(name)

    def _user_gen(self):
        yield 'USLACKBOT', 'slackbot'

        pages = self._wc._get_pages(urls['users'])
        for page in pages:
            for user in page['members']:
                yield user['id'], user['name']

    def _channel_gen(self):
        pages = self._wc._get_pages(urls['convos'], 
                types='public_channel,private_channel,mpim,im')

        for page in pages:
            for c in page['channels']:
                if c['id'][0] == 'D':
                    # is im, use username as name
                    yield c['id'], self.user_name(c['user'])
                else:
                    yield c['id'], c['name']

class Cache(object):
    """ Generic locking KV store """

    def __init__(self):
        self._lock = Lock()
        self._items = {} # mapping of id to name

    def reset(self):
        self._items = {}

    def id_to_name(self, sid):
        """ lookup Slack name by ID """
        self.lock()
        try:
            return self._items.get(sid, 'unknown')
        finally:
            self.unlock()

    def name_to_id(self, name):
        """ lookup Slack name by ID """
        self.lock()
        try:
            for k,v in self._items.items():
                if v == name:
                    return k
            return 'unknown'
        finally:
            self.unlock()

    def update(self, item_gen):
        self.lock()
        try:
            self._items = dict(item_gen())
        finally:
            self.unlock()

    def lock(self):
        self._lock.acquire()

    def unlock(self):
        self._lock.release()

