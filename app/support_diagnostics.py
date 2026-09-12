"""Content-free Desktop support report. No network, campaign data or secrets."""
import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from version_info import __version__

PACKAGES = ('fastapi', 'uvicorn', 'Pillow', 'fpdf2', 'python-docx', 'resvg-py', 'requests')


def report():
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = 'not installed'
    return {
        'schema': 1,
        'app_version': __version__,
        'python_version': platform.python_version(),
        'operating_system': platform.system(),
        'machine_architecture': platform.machine(),
        'packages': packages,
        'missing_packages': [name for name, value in packages.items() if value == 'not installed'],
        'notice': 'Installation inventory only. No usernames, paths, hostnames, keys, prompts, clients, tokens or campaign files included. Not a native OS certification.',
    }


if __name__ == '__main__':
    json.dump(report(), sys.stdout, indent=2)
    print()
