"""Update check — reassurance that a one-time-purchase product is still
maintained, without telemetry.

One GET to api.github.com for the latest release tag. No identifiers, no
payload, no analytics — and because it goes through `requests`, the request
itself appears in the network ledger (net_audit), so the app never makes a
covert outbound call. Set BRANDFORGE_UPDATE_CHECK=0 to disable entirely;
offline machines simply get {"error": ...} and carry on.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

RELEASES_URL = "https://api.github.com/repos/nabsan144-hub/brandforge-os/releases/latest"
DEFAULT_TIMEOUT = 10


def enabled() -> bool:
    """Opt-in by environment only. The dashboard's one-time consent prompt is
    stored separately (engine config 'update_check'); the caller ORs the two.
    A privacy-first product must not phone home by default — the ledger
    would show the contradiction on a fresh install."""
    return os.environ.get("BRANDFORGE_UPDATE_CHECK", "0").strip().lower() in ("1", "true", "yes", "on")


def allowed(consent: bool = False) -> bool:
    raw = os.environ.get('BRANDFORGE_UPDATE_CHECK')
    if raw is not None:
        return enabled()
    return bool(consent)


def parse_version(tag: str) -> Optional[Tuple[int, ...]]:
    """'v1.2.23' / '1.2.23' -> (1, 2, 23). Anything unparseable -> None
    (an unexpected tag must never crash the app or fake an update)."""
    m = re.match(r"^v?(\d+(?:\.\d+)*)", str(tag or "").strip())
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    # pad so (1,2) vs (1,2,0) compare equal, not by length
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return a > b


def check_for_update(current_version: str, timeout: int = DEFAULT_TIMEOUT, *, consent: bool = False) -> Dict[str, Any]:
    """Returns {current, latest, update_available, checked_at, error}.
    Never raises — network failures are data, not crashes."""
    result: Dict[str, Any] = {
        "current": current_version,
        "latest": None,
        "update_available": False,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "error": None,
    }
    if not (enabled() or allowed(consent)):
        result["error"] = "disabled"
        return result
    try:
        import requests
        resp = requests.get(RELEASES_URL, timeout=timeout,
                            headers={"Accept": "application/vnd.github+json"})
        if resp.status_code == 404:
            # repo has no releases yet — not an error worth surfacing
            result["error"] = "no_releases"
            return result
        resp.raise_for_status()
        tag = (resp.json() or {}).get("tag_name") or ""
        result["latest"] = str(tag)[:40] or None
        result["update_available"] = is_newer(tag, current_version)
    except Exception as exc:  # noqa: BLE001 — offline is a normal state
        result["error"] = type(exc).__name__
    return result
