from threading import Lock

from .config import urls
from .models import User, Channel, DirItem

def cached(fn):
    """ decorator to provide cache refreshing on failed lookups """
    def wrap(obj, *args):
        res = fn(obj, *args)
        if not res:
            # reload cache and try again
            obj.refresh()
            res = fn(obj, *args)
        return res if res else DirItem({})
    return wrap

class Directory(object):
    def __init__(self, webclient):
        self._wc = webclient
        self._users = Cache()
        self._channels = Cache()

    def refresh(self):
        self._users.update(self._user_gen)
        self._channels.update(self._channel_gen)

    @cached
    def user(self, match):
        """ Lookup User object by id or name """
        if len(match) == 9 and match[0] == 'U':
            return self._users.lookup('id', match)
        return self._users.lookup('name', match)

    @cached
    def channel(self, match):
        """ Lookup Channel object by id or name """
        if len(match) == 9 and match[0] in ('C','G','D'):
            return self._channels.lookup('id', match)
        return self._channels.lookup('name', match)

    def _user_gen(self):
        for page in self._wc._get_pages(urls['users']):
            for  data in page['members']:
                yield User(data)

    def _channel_gen(self):
        pages = self._wc._get_pages(urls['convos'], 
                types='public_channel,private_channel,mpim,im')

        for page in pages:
            for cdata in page['channels']:
                chan = Channel(cdata)
                # if im, use username as name
                if chan.id[0] == 'D':
                    chan.name = self.user(chan['user']).name
                yield chan

class Cache(object):
    """ Generic locking KV store """

    def __init__(self):
        self._lock = Lock()
        self._items = [] # list of DirItem objects

    def lookup(self, attr, val):
        """ lookup DirItem object with attribute matching value """
        self.lock()
        try:
            for x in self._items:
                if getattr(x, attr) == val:
                    return x
        finally:
            self.unlock()

    def update(self, item_gen):
        self.lock()
        try:
            self._items = list(item_gen())
        finally:
            self.unlock()

    def lock(self):
        self._lock.acquire()

    def unlock(self):
        self._lock.release()

