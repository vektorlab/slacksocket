from threading import Lock

class ObjectCache(object):
    """ Generic list of objects from Slack API """

    def __init__(self):
        self._lock = Lock()
        self._items = []

    def match(self, key, value):
        """ lookup object by key and value """
        self.lock()
        try:
            return self._match(key, value)
        finally:
            self.unlock()

    def _match(self, k, v):
        for o in self._items:
            if o.get(k) == v:
                return o
        return {}

    def update(self, items):
        self.lock()
        self._items = items
        self.unlock()

    def lock(self):
        self._lock.acquire()

    def unlock(self):
        self._lock.release()

