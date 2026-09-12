"""Real AI image generation for online campaigns.

The default endpoint is Pollinations.ai (free, public, no key). The optional
``BRANDFORGE_IMAGE_ENDPOINT`` override is an operator setting that is now
validated for SSRF the same way ``web_searcher`` validates outbound URLs:
loopback/private/link-local hosts (including cloud metadata endpoints) are
refused, whether given as IP literals or as hostnames that resolve there.
Offline and Ollama campaign modes never call this module.
"""

from __future__ import annotations

import ipaddress
import math
import os
import re
import socket
import urllib.parse
from typing import Optional
from modules.public_http import fetch_public

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

DEFAULT_ENDPOINT = "https://image.pollinations.ai/prompt/{prompt}"

# Same private/loopback/link-local blocklist as modules/web_searcher.py —
# keep the two lists in sync.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network('0.0.0.0/8'),      # "this network" — resolves to loopback on Linux
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),  # link-local incl. cloud metadata
    ipaddress.ip_network('100.64.0.0/10'),   # CGNAT
    ipaddress.ip_network('198.18.0.0/15'),   # benchmarking / some CDN backends
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),        # ULA
    ipaddress.ip_network('fe80::/10'),       # IPv6 link-local
]


def _endpoint() -> str:
    # Read at call time so an operator setting the variable before a long-lived
    # process's next campaign is respected; tests and embedded deployments can
    # also override it without re-importing the module.
    return os.environ.get("BRANDFORGE_IMAGE_ENDPOINT", "").strip() or DEFAULT_ENDPOINT


def _ip_blocked(ip_str: str) -> bool:
    """True if an IP literal is loopback/private/link-local (incl. v4-mapped v6)."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Not an IP literal; fail closed if it looks like a mangled IPv6.
        return ip_str.count(':') >= 2
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        for net in _BLOCKED_NETWORKS:
            if mapped in net:
                return True
    return False


def _endpoint_url_safe(url: str) -> bool:
    """SSRF guard for the (possibly operator-overridden) image endpoint.

    Blocks IP-literal hosts in the blocklist, then resolves hostnames and
    blocks if ANY resolved address is private/loopback/link-local — the same
    policy ``web_searcher`` already enforces for outbound research requests.
    Fails closed on any error.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        netloc = (parsed.netloc or "").split("@")[-1]
        # Unbracketed IPv6 in the authority is invalid per RFC 3986 — fail closed.
        if netloc.count(":") >= 2 and not netloc.startswith("["):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        hostname = hostname.lower()
        if hostname in ("localhost", "metadata.google.internal"):
            return False
        # IP-literal host: check directly.
        try:
            ipaddress.ip_address(hostname)
            return not _ip_blocked(hostname)
        except ValueError:
            pass
        if _ip_blocked(hostname):  # mangled IPv6-looking hostnames fail closed
            return False
        # Hostname: block if ANY resolved address is blocked (DNS-rebinding
        # mitigation, same accepted race window as web_searcher).
        infos = socket.getaddrinfo(hostname, None)
        if not infos:
            return False
        for info in infos:
            if _ip_blocked(info[4][0]):
                return False
        return True
    except Exception:
        return False


def generate_image_bytes(
    prompt: str, width: int = 1200, height: int = 630, timeout: int = 30, seed: int = None
) -> Optional[bytes]:
    """Return validated JPEG/PNG bytes, or ``None`` on any failure.

    This function deliberately never raises; callers retain the deterministic
    SVG deliverables when a remote image service is unavailable.
    """
    if requests is None or not prompt:
        return None
    clean = re.sub(r"[^\w\s,.\-&]", "", str(prompt))[:200].strip()
    if not clean:
        return None
    try:
        w = max(256, min(int(width or 1200), 2048))
        h = max(256, min(int(height or 630), 2048))
        request_timeout = max(1, min(int(timeout or 30), 60))
        params = {"width": w, "height": h, "nologo": "true", "model": "flux", "safe": "true"}
        if seed is not None:
            seed_value = int(seed)
            if not math.isfinite(seed_value):
                return None
            params["seed"] = seed_value
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        url = _endpoint().format(prompt=urllib.parse.quote(clean))
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        if not _endpoint_url_safe(url):
            return None
        url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        response = fetch_public(url, timeout=request_timeout, max_bytes=10_000_000)
        content = response.content
        if len(content) > 10_000_000:
            return None
        if response.status_code == 200 and (
            content.startswith(b"\xff\xd8\xff") or content.startswith(b"\x89PNG\r\n\x1a\n")
        ):
            from modules.ai_image_designer import _valid_image_bytes
            return _valid_image_bytes(content)
    except Exception:
        return None
    return None
