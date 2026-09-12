#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# One validated implementation on Windows, macOS and Linux; no sed injection.
exec "${PYTHON:-python3}" scripts/set_site_url.py "${1:-${SITE_URL:-}}"
