"""Compatibility entry point for the canonical browser regression suite.

Serve sales on 8765 and (optionally) isolated Desktop on 8767. Set
BRANDFORGE_DESKTOP_QA=1 to include Desktop. Third-party Cloud state is mocked.
Failures propagate as a nonzero exit; no fixed global output paths are used.
"""
import runpy
from pathlib import Path
if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('browser_regressions.py')), run_name='__main__')
