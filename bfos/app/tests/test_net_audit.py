"""Phase 3 (§3.1): the network ledger must make "offline = 0 outbound
requests" a verifiable claim, not a badge.

These tests exercise the REAL wrapper around requests.sessions.Session.request
against a real local HTTP server — no mocked ledger, no reimplementation.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from modules.net_audit import LEDGER, install


@pytest.fixture()
def ledger():
    """Fresh ledger per test; LEDGER is process-global state."""
    LEDGER.reset()
    yield LEDGER
    LEDGER.reset()


def _local_server():
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def test_install_is_idempotent():
    assert install() in (True, False)  # first-ever install or already done
    assert install() is False          # never double-wraps


def test_real_request_is_recorded(ledger):
    import requests
    srv = _local_server()
    try:
        port = srv.server_address[1]
        r = requests.get(f"http://127.0.0.1:{port}/anything", timeout=5)
        assert r.status_code == 200
        snap = ledger.snapshot()
        assert snap["total_requests"] >= 1
        assert snap["by_host"].get("127.0.0.1") >= 1
        assert any(e["host"] == "127.0.0.1" and e["status"] == 200 for e in snap["recent"])
    finally:
        srv.shutdown()


def test_failed_request_is_recorded(ledger):
    import requests
    before = ledger.snapshot()["total_requests"]
    with pytest.raises(Exception):
        # port 1 on loopback: connection refused, fast
        requests.get("http://127.0.0.1:1/nope", timeout=2)
    snap = ledger.snapshot()
    assert snap["total_requests"] == before + 1
    assert snap["failed"] >= 1
    assert any(e["error"] for e in snap["recent"])


def test_only_host_is_recorded_never_full_url(ledger):
    """API keys ride in query strings (Gemini ?key=...) — the ledger must
    never store them."""
    import requests
    srv = _local_server()
    try:
        port = srv.server_address[1]
        requests.get(f"http://127.0.0.1:{port}/x?key=SUPERSECRET123", timeout=5)
        blob = json.dumps(ledger.snapshot())
        assert "SUPERSECRET123" not in blob
        assert "/x" not in blob  # paths are not stored either
    finally:
        srv.shutdown()


def test_offline_swarm_makes_zero_outbound_requests(client, ledger):
    """THE headline proof: a full campaign generation in offline mode issues
    zero network requests of any kind."""
    ledger.reset()
    r = client.post("/api/swarm/run", json={
        "campaign_name": "Net audit zero", "product_name": "Offline Coffee",
        "industry": "Retail", "target_audience": "Remote workers",
        "key_benefits": "Fresh, fast"})
    assert r.status_code == 200, r.text
    snap = ledger.snapshot()
    assert snap["total_requests"] == 0, (
        f"offline generation must not touch the network, got: {snap['by_host']}")


def test_network_audit_endpoint_shape(client, ledger):
    r = client.get("/api/network-audit")
    assert r.status_code == 200
    data = r.json()
    for key in ("session_started", "total_requests", "external_requests",
                "failed", "by_host", "recent"):
        assert key in data
