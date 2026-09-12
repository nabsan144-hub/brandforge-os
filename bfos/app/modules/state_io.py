"""Read local JSON state without turning corruption into an empty replacement."""
import json


class LocalStateError(RuntimeError):
    pass


def read_object(path, *, maximum=16_000_000):
    try:
        with open(path, 'rb') as handle:
            raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError('oversize state')
        def invalid_constant(_):
            raise ValueError('nonfinite JSON')
        value = json.loads(raw, parse_constant=invalid_constant)
        if not isinstance(value, dict):
            raise ValueError('state must be an object')
        return value
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError) as exc:
        raise LocalStateError('Local data is unreadable or exceeds its safety limit. It was not replaced. Preserve the file and restore a valid backup before retrying.') from exc
