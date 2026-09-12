"""One data-directory policy for portable installs, wheels and explicit overrides."""
import os
import sys
from pathlib import Path


def data_dir():
    override = os.environ.get('BRANDFORGE_DATA_DIR', '').strip()
    if override:
        return str(Path(override).expanduser().resolve())
    portable = Path(__file__).resolve().parents[1]
    if not getattr(sys, 'frozen', False) and (portable / 'pyproject.toml').is_file() and os.access(portable, os.W_OK):
        return str(portable)
    if os.name == 'nt':
        root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local')
    elif sys.platform == 'darwin':
        root = Path.home() / 'Library/Application Support'
    else:
        root = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return str(root / 'BrandForgeOS')


def dashboard_dir():
    root = Path(__file__).resolve().parents[1]
    packaged = root / 'brandforge_assets/dashboard'
    return str(packaged if (packaged / 'index.html').is_file() else root / 'web/dist')
