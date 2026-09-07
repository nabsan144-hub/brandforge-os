"""MEDIUM-02 regression: blind cross-origin CSRF against the unauthenticated
local API. A malicious page in another tab can send "simple" POSTs
(text/plain, no preflight) to localhost — the response stays unreadable but
the request used to execute. Now any state-changing request carrying a
foreign Origin/Referer is refused; header-less clients (CLI, curl, Swagger
UI, tests) are unaffected."""


def _post_state_change(client, headers=None):
    return client.post("/api/tools/execute",
                       json={"tool_name": "list_templates", "args": {}},
                       headers=headers or {})


def test_foreign_origin_blocked(client):
    r = _post_state_change(client, {"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert "Cross-origin request blocked" in r.text


def test_foreign_referer_blocked(client):
    r = _post_state_change(client, {"Referer": "http://evil.example/attack.html"})
    assert r.status_code == 403


def test_null_origin_blocked(client):
    # sandboxed-iframe Origin — treat as foreign, fail closed
    r = _post_state_change(client, {"Origin": "null"})
    assert r.status_code == 403


def test_same_origin_allowed(client):
    # TestClient's Host header is "testserver"; a same-origin POST is fine
    r = _post_state_change(client, {"Origin": "http://testserver"})
    assert r.status_code != 403


def test_configured_dev_origin_allowed(client):
    # default BRANDFORGE_CORS_ORIGINS includes the Vite dev server
    r = _post_state_change(client, {"Origin": "http://localhost:5173"})
    assert r.status_code != 403


def test_no_origin_header_still_works(client):
    # CLI, curl, Swagger UI, existing tests: no Origin/Referer at all
    r = _post_state_change(client)
    assert r.status_code != 403
    r2 = client.post("/api/chat", json={"message": "hi"})
    assert r2.status_code != 403


def test_get_requests_unaffected(client):
    r = client.get("/api/campaigns", headers={"Origin": "http://evil.example"})
    assert r.status_code != 403  # reads are CORS-protected, not CSRF-relevant
