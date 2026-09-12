#!/usr/bin/env bash
# Use the managed environment created by explicit setup; never install on launch.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
else
    echo "Install Python 3.10+ and run python app/setup_env.py --install." >&2
    exit 1
fi
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)'
exec "$PYTHON" "$SCRIPT_DIR/brandforge.py" "$@"
