"""Recoverable updates to the two local settings files; journal is private.

This coordinates a single Desktop writer. A crash between replacements leaves
an undo journal; startup restores the previous pair before reading credentials.
Never log journal contents or expose this directory through an HTTP mount.
"""
import base64
import json
from pathlib import Path
from modules.security import atomic_write_bytes, atomic_write_json
from modules.state_locks import state_lock

MAX_SETTINGS_BYTES = 1_000_000
JOURNAL = '.settings-transaction.json'
FILES = ('config.json', '.env')


class SettingsStorageError(RuntimeError):
    pass


def _read(path):
    try:
        with path.open('rb') as handle:
            value = handle.read(MAX_SETTINGS_BYTES + 1)
        if len(value) > MAX_SETTINGS_BYTES:
            raise SettingsStorageError('Settings exceed the supported size; existing files were preserved.')
        return value
    except FileNotFoundError:
        return None


def _restore(root, previous):
    for name in FILES:
        value = previous[name]
        if value is None:
            (root / name).unlink(missing_ok=True)
        else:
            atomic_write_bytes(str(root / name), value, mode=0o600)


def recover(root):
    root = Path(root)
    with state_lock(str(root)):
        path = root / JOURNAL
        if not path.exists():
            return False
        try:
            with path.open('rb') as handle:
                raw = handle.read(3 * MAX_SETTINGS_BYTES + 1)
            if len(raw) > 3 * MAX_SETTINGS_BYTES:
                raise ValueError('oversize journal')
            data = json.loads(raw)
            if data.get('schema') != 1 or set(data['previous']) != set(FILES):
                raise ValueError('invalid journal')
            previous = {}
            for name, encoded in data['previous'].items():
                value = None if encoded is None else base64.b64decode(encoded, validate=True)
                if value is not None and len(value) > MAX_SETTINGS_BYTES:
                    raise ValueError('invalid snapshot')
                previous[name] = value
            _restore(root, previous)
            path.unlink()
            return True
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise SettingsStorageError('An interrupted settings update could not be recovered. Preserve the data folder and restore a verified backup before retrying.') from exc


def commit(root, config, env_text):
    root = Path(root)
    with state_lock(str(root)):
        root.mkdir(parents=True, exist_ok=True)
        recover(root)
        try:
            previous = {name: _read(root / name) for name in FILES}
            desired = {'config.json': (json.dumps(config, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'),
                       '.env': env_text.encode('utf-8')}
            if any(len(data) > MAX_SETTINGS_BYTES for data in desired.values()):
                raise ValueError('oversize settings')
            journal = {'schema': 1, 'previous': {name: None if data is None else base64.b64encode(data).decode('ascii') for name, data in previous.items()}}
            atomic_write_json(str(root / JOURNAL), journal, mode=0o600)
            # Both replacements are individually atomic; the journal covers
            # a crash between them. Runtime state changes only after success.
            for name in ('.env', 'config.json'):
                atomic_write_bytes(str(root / name), desired[name], mode=0o600)
            (root / JOURNAL).unlink()
        except (OSError, ValueError, TypeError) as exc:
            if (root / JOURNAL).exists():
                recover(root)
            raise SettingsStorageError('Settings were not saved. Check disk space and data-folder permissions; no successful save was confirmed.') from exc
