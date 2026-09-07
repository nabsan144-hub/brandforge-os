"""Release version: pyproject in a source/portable install; wheel metadata otherwise."""
import re
from pathlib import Path
from importlib.metadata import version

source = Path(__file__).with_name('pyproject.toml')
if source.exists():
    match = re.search(r'^version\s*=\s*"([^"]+)"',source.read_text(encoding='utf-8'),re.M)
    if not match: raise RuntimeError('Release version missing from pyproject.toml')
    __version__ = match.group(1)
else:
    __version__ = version('brandforge-os')
