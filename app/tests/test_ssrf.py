import pytest
import socket
import sys
import types

from modules.web_searcher import WebSearcher

BLOCKED = [
    "http://127.0.0.1:8000/health",
    "http://10.0.0.5/x",
    "http://172.16.0.1/x",
    "http://192.168.1.10/x",
    "http://169.254.169.254/latest/meta-data/",
    "http://localhost:8000/",
    "http://metadata.google.internal/",
    "file:///etc/passwd",
    "ftp://example.com/x",
    "http://[::1]/x",
    "http://[fc00::1]/x",
    "http://fc00::1/x",
    "http://[::ffff:127.0.0.1]/x",
]

@pytest.mark.parametrize("url", BLOCKED)
def test_blocked(url):
    assert WebSearcher()._is_blocked_url(url) is True


def test_public_allowed():
    assert WebSearcher()._is_blocked_url("https://example.com") is False
    assert WebSearcher()._is_blocked_url("https://example.com/path?q=1") is False


def test_search_returns_real_or_empty_never_fake():
    """Offline or challenged → []. Never a synthetic duckduckgo link row."""
    ws = WebSearcher()
    results = ws.search("brandforge os test query 12345", max_results=3)
    assert isinstance(results, list)
    for r in results:
        assert "duckduckgo.com/?q=" not in r.get("url", ""), "synthetic result leaked"


def test_format_summary_honest_when_empty():
    ws = WebSearcher()
    out = ws.format_search_summary("anything", [])
    assert "unavailable" in out.lower()


# ---------- DNS-rebinding / SSRF regression tests ----------
# A hostname that is not an IP literal passes _is_blocked_url(); safety then
# depends on _host_resolves_safe being called on EVERY network path.

def _mock_dns(monkeypatch, mapping):
    """Point hostnames at fixed IPs without touching the network."""
    real_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, *a, **k):
        if host in mapping:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (mapping[host], 0))]
        return real_getaddrinfo(host, *a, **k)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


class _FakeRoute:
    def __init__(self):
        self.action = None

    def fulfill(self, **kwargs):
        self.action = "fulfilled"

    def continue_(self):
        self.action = "continue"
        return None

    def abort(self):
        self.action = "abort"
        return None


class _FakePage:
    def __init__(self, state):
        self._state = state

    def route(self, pattern, handler):
        self._state["handler"] = handler

    def goto(self, url, **kwargs):
        self._state["goto"].append(url)
        return None

    def content(self):
        return "<html><head><title>T</title></head><body>ok</body></html>"

    def title(self):
        return "T"

    def inner_text(self, _sel):
        return "ok"


class _FakeBrowser:
    def __init__(self, state):
        self._state = state

    def new_context(self, **kwargs):
        return self

    def route_web_socket(self, *args):
        pass

    def add_init_script(self, *args):
        pass

    def route(self, pattern, handler):
        self._state['handler'] = handler

    def new_page(self):
        return _FakePage(self._state)

    def close(self):
        pass


def _install_fake_playwright(monkeypatch, state):
    """Stub the playwright import so browser_audit's real-browser path runs
    without Chromium; records goto() calls and the installed route guard."""
    import types

    class _Sync:
        def __enter__(self):
            return types.SimpleNamespace(chromium=types.SimpleNamespace(
                launch=lambda **k: _FakeBrowser(state)))

        def __exit__(self, *a):
            return False

    pw = types.ModuleType("playwright")
    pw_api = types.ModuleType("playwright.sync_api")
    pw_api.sync_playwright = lambda: _Sync()
    pw.sync_api = pw_api
    monkeypatch.setitem(sys.modules, "playwright", pw)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", pw_api)


def test_fetch_html_blocks_domain_resolving_to_private_ip(monkeypatch):
    _mock_dns(monkeypatch, {"evil.test": "10.0.0.5"})
    ws = WebSearcher()
    assert ws.fetch_html("http://evil.test") == ""
    assert ws.fetch_html("http://metadata-rebind.test/") == ""  # unresolvable → blocked


def test_browser_audit_blocks_domain_resolving_to_private_ip(monkeypatch):
    """HIGH-01 regression: a domain resolving to an internal IP must never
    reach page.goto() — previously only IP *literals* were checked."""
    _mock_dns(monkeypatch, {"evil.test": "10.0.0.5"})
    state = {"goto": [], "handler": None}
    _install_fake_playwright(monkeypatch, state)
    ws = WebSearcher()
    result = ws.browser_audit("http://evil.test")
    assert result.get("method") == "blocked"
    assert "Blocked" in result.get("error", "")
    assert state["goto"] == [], "Chrome must not be pointed at a private target"


def test_browser_audit_allows_public_domain(monkeypatch):
    _mock_dns(monkeypatch, {"good.test": "93.184.216.34"})
    state = {"goto": [], "handler": None}
    _install_fake_playwright(monkeypatch, state)
    ws = WebSearcher()
    result = ws.browser_audit("http://good.test")
    assert result.get("method") == "playwright_real_browser"
    assert state["goto"] == ["http://good.test"]


def test_browser_audit_redirect_guard(monkeypatch):
    """Every hop Chrome is about to make — redirect targets included — must
    pass the same block checks via the page.route guard."""
    _mock_dns(monkeypatch, {
        "good.test": "93.184.216.34",
        "rebind.test": "169.254.169.254",   # domain → cloud metadata IP
    })
    state = {"goto": [], "handler": None}
    _install_fake_playwright(monkeypatch, state)
    ws = WebSearcher()
    assert ws.browser_audit("http://good.test").get("method") == "playwright_real_browser"
    from modules import public_http
    def exchange(parsed,*args):
        return public_http.PublicResponse(200,{'content-type':'text/html'},b'<html/>',parsed.geturl())
    monkeypatch.setattr(public_http, '_exchange', exchange)
    guard = state["handler"]
    assert guard is not None, "browser_audit must install a per-request route guard"

    def _check(url):
        route = _FakeRoute()
        guard(route, types.SimpleNamespace(url=url, method="GET"))
        return route.action

    assert _check("http://good.test/next-page") == "fulfilled"
    assert _check("http://169.254.169.254/latest/meta-data/") == "abort"
    assert _check("http://rebind.test/x") == "abort"          # DNS rebind mid-session
    assert _check("http://10.0.0.5/internal") == "abort"
    assert _check("data:image/png;base64,AAAA") == "continue"  # never touches network
