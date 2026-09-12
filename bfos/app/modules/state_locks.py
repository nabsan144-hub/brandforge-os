"""Shared in-process locks for managers addressing the same local data folder.

Desktop is a single-instance application; separate processes must not edit the
same data folder concurrently. SQLite transactions still protect SQL records.
"""
import os
import threading
import weakref

_guard = threading.Lock()
_locks = weakref.WeakValueDictionary()


def state_lock(base):
    key = os.path.normcase(os.path.realpath(base))
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock
