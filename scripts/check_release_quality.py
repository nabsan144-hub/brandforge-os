"""Required local release gates. This does not authorize payment activation.

Use a cleaned, disk-backed scratch directory: repeated raster/PDF test runs
must not accumulate in a RAM-backed /tmp and starve the PostgreSQL/WASM tests.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    [sys.executable, '-m', 'pytest', 'app/tests', '-q'],
    [sys.executable, '-m', 'ruff', 'check', 'app'],
    ['npm', 'test', '--prefix', 'cloud'],
    ['npm', 'test', '--prefix', 'sales'],
    ['npm', 'run', 'build', '--prefix', 'sales'],
    ['npm', 'run', 'build', '--prefix', 'app/web-modern'],
    ['node', 'cloud/scripts/sync-schema.mjs', '--check'],
    [sys.executable, 'scripts/validate_launch_config.py', '--prelaunch'],
]


def main():
    env = dict(os.environ)
    # Source verification never authorizes a production checkout.
    for key in ('CLOUD_CHECKOUT_ENABLED', 'DESKTOP_CHECKOUT_ENABLED'):
        env[key] = 'false'
    scratch = ROOT / '.cache' / 'release-tests'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='run-', dir=scratch) as temporary:
        for key in ('TMPDIR', 'TMP', 'TEMP'):
            env[key] = temporary
        for command in COMMANDS:
            print('QUALITY:', ' '.join(command), flush=True)
            subprocess.run(command, cwd=ROOT, env=env, check=True)


if __name__ == '__main__':
    main()
