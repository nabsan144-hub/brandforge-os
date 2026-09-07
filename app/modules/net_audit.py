"""Tracked requests-library and bounded public-fetch HTTP calls (hosts/status/duration only).

Not an exhaustive egress monitor: urllib, httpx, browser fetches, dependency
installation, model runtimes and other processes can bypass this hook. A zero
counter is not proof of zero network traffic. See docs/NETWORK-PRIVACY.md.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

_MAX_ENTRIES = 200  # ring buffer: recent detail; totals are exact forever

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


class NetworkLedger:
    """Thread-safe outbound-request ledger with exact totals + recent detail."""

    def __init__(self, max_entries: int = _MAX_ENTRIES) -> None:
        self._lock = threading.Lock()
        self._entries: "deque[Dict[str, Any]]" = deque(maxlen=max_entries)
        self._total = 0
        self._failed = 0
        self._by_host: Dict[str, int] = {}
        self._started_at = datetime.now().isoformat(timespec="seconds")

    def record(self, method: str, url: str, status: Optional[int] = None,
               elapsed_ms: Optional[int] = None, error: Optional[str] = None) -> None:
        try:
            host = (urlparse(str(url)).hostname or '<invalid-url>').lower()
        except ValueError:
            host = '<invalid-url>'
        entry = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "method": str(method).upper()[:10],
            "host": host,
            "local": host in _LOOPBACK_HOSTS,
            "status": status,
            "elapsed_ms": elapsed_ms,
            "error": error,
        }
        with self._lock:
            self._entries.append(entry)
            self._total += 1
            if error or status is None or status >= 400:
                self._failed += 1
            if host not in self._by_host and len(self._by_host) >= 4096:
                host = '<additional-hosts>'
            self._by_host[host] = self._by_host.get(host, 0) + 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_started": self._started_at,
                "scope": "requests-library and bounded public-fetch calls; not an exhaustive network monitor",
                "total_requests": self._total,
                "external_requests": sum(
                    c for h, c in self._by_host.items() if h not in _LOOPBACK_HOSTS
                ),
                "failed": self._failed,
                "by_host": dict(sorted(self._by_host.items(), key=lambda kv: -kv[1])),
                "recent": list(self._entries)[-50:],
            }

    def reset(self) -> None:
        """Test hook — clears counters so a scenario can prove '0 requests'."""
        with self._lock:
            self._entries.clear()
            self._total = 0
            self._failed = 0
            self._by_host.clear()
            self._started_at = datetime.now().isoformat(timespec="seconds")


LEDGER = NetworkLedger()

_install_lock = threading.Lock()
_installed = False


def install(ledger: Optional[NetworkLedger] = None) -> bool:
    """Wrap requests' Session.request once. Idempotent; returns True the
    first time it actually installs. Failures inside the wrapper must never
    break the underlying request — auditing is best-effort, traffic is not."""
    global _installed
    with _install_lock:
        if _installed:
            return False
        import requests  # imported late so module import has no side effects
        target = ledger or LEDGER
        original = requests.sessions.Session.request

        def audited_request(self, method, url, *args, **kwargs):
            started = time.monotonic()
            try:
                response = original(self, method, url, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — record, then re-raise untouched
                try:
                    target.record(method, url,
                                  elapsed_ms=int((time.monotonic() - started) * 1000),
                                  error=type(exc).__name__)
                except Exception:
                    pass
                raise
            try:
                target.record(method, url, status=getattr(response, "status_code", None),
                              elapsed_ms=int((time.monotonic() - started) * 1000))
            except Exception:
                pass
            return response

        requests.sessions.Session.request = audited_request  # type: ignore[method-assign]
        _installed = True
        return True
