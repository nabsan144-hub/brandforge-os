"""Bounded ephemeral local job visibility; no prompts, keys or provider payloads."""
from copy import deepcopy
import threading
import time
from uuid import UUID, uuid4

_LOCK = threading.Lock()
_JOBS = {}


def start(request_id=None):
    key = str(UUID(request_id)) if request_id else str(uuid4())
    with _LOCK:
        now = time.monotonic()
        for old in list(_JOBS):
            if now - _JOBS[old]['at'] > 600:
                del _JOBS[old]
        if key in _JOBS:
            raise ValueError('This request was already submitted; check campaign history.')
        if len(_JOBS) >= 64:
            raise ValueError('Job history is temporarily full. Wait before starting another campaign.')
        _JOBS[key] = {'at': now, 'status': 'running', 'stages': {}}
    return key


def update(key, stage, state):
    if stage not in {'research', 'strategy', 'copy', 'review', 'visuals', 'seo', 'artwork', 'packaging'} or state not in {'running', 'complete'}:
        return
    with _LOCK:
        if key in _JOBS and _JOBS[key]['status'] == 'running':
            _JOBS[key]['stages'][stage] = state


def finish(key, status):
    with _LOCK:
        if key in _JOBS:
            _JOBS[key]['status'] = status


def read(key):
    with _LOCK:
        row = _JOBS.get(key)
        if not row or time.monotonic() - row['at'] > 600:
            return None
        return {'request_id': key, 'status': row['status'], 'stages': deepcopy(row['stages'])}
