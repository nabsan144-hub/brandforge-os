"""Explicit setup/repair. Ordinary checks are local and never invoke pip.

The fingerprint records requirements, interpreter environment and installed
versions. It is a readiness check, not a proof against filesystem tampering.
This bootstrap uses only the Python standard library until dependencies exist.
"""
from __future__ import annotations
import argparse
import hashlib
from importlib import metadata
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'setup-state.json'
REQUIREMENTS = ROOT / 'requirements.txt'


def fingerprint():
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def installed_versions():
    names = []
    for line in REQUIREMENTS.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_.-]*)\s*(?:[<>=!~].*)?', line)
        if not match:
            raise RuntimeError('Unsupported core requirement entry; setup must be reviewed.')
        names.append(match[1])
    if not names:
        raise RuntimeError('No core dependencies were listed.')
    return {name: metadata.version(name) for name in names}


def binding():
    return {'python': f'{sys.version_info.major}.{sys.version_info.minor}',
            'environment': str(Path(sys.prefix).resolve())}


def configured():
    try:
        data = json.loads(STATE.read_text(encoding='utf-8'))
        return (isinstance(data, dict) and data.get('schema') == 2
                and data.get('requirements_sha256') == fingerprint()
                and all(data.get(k) == v for k, v in binding().items())
                and data.get('versions') == installed_versions())
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, metadata.PackageNotFoundError):
        return False


def record():
    data = {'schema': 2, 'requirements_sha256': fingerprint(), **binding(),
            'versions': installed_versions(), 'installed_at': datetime.now(timezone.utc).isoformat()}
    fd, name = tempfile.mkstemp(prefix='.setup-state-', suffix='.tmp', dir=ROOT)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.replace(name, STATE)
    finally:
        Path(name).unlink(missing_ok=True)


def install():
    if sys.version_info < (3, 10):
        raise RuntimeError('Python 3.10 or newer is required')
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(ROOT / '.venv')], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(REQUIREMENTS)], check=True)
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    subprocess.run([str(python), str(Path(__file__)), '--record'], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--install', action='store_true')
    mode.add_argument('--record', action='store_true')
    args = parser.parse_args()
    if args.check:
        if configured():
            print('Local setup fingerprint and dependency versions are current.')
            return 0
        print('Setup is missing, incomplete or changed. Run SETUP-WINDOWS.bat, or python app/setup_env.py --install, while online.')
        return 1
    if args.record:
        record()
        return 0
    install()
    print('Setup complete. Normal launch will not run pip.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, metadata.PackageNotFoundError) as error:
        print(f'Setup failed ({type(error).__name__}); no successful setup was recorded.', file=sys.stderr)
        sys.exit(1)
