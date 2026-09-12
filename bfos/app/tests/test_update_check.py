"""Phase 3 (§3.2): update check — comparator correctness + failure modes.
The HTTP layer is monkeypatched; the real check_for_update code runs."""
import pytest

from modules import update_check
from modules.update_check import check_for_update, is_newer, parse_version


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    # comparator/failure-mode tests assume the env opt-in; consent-gate and
    # default-off tests override this explicitly.
    monkeypatch.setenv("BRANDFORGE_UPDATE_CHECK", "1")


@pytest.fixture(autouse=True)
def _no_leaked_update_worker():
    yield
    # The consent-gate worker is a daemon thread writing shared module state;
    # a leftover worker publishing mid-next-test was the cross-test pollution
    # behind the full-suite flake. Join any survivor after each test.
    import threading
    for t in threading.enumerate():
        if t.name == "update-check" and t is not threading.current_thread():
            t.join(timeout=10)


def test_parse_version_variants():
    assert parse_version("v1.2.23") == (1, 2, 23)
    assert parse_version("1.2") == (1, 2)
    assert parse_version("  v10.0.1 ") == (10, 0, 1)
    assert parse_version("garbage") is None
    assert parse_version("") is None
    assert parse_version(None) is None


def test_is_newer_matrix():
    assert is_newer("v1.3.0", "1.2.23") is True
    assert is_newer("v1.2.24", "v1.2.23") is True
    assert is_newer("v1.2.23", "v1.2.23") is False
    assert is_newer("v1.2.2", "v1.2.23") is False
    assert is_newer("v1.2", "v1.2.0") is False       # padding: equal, not newer
    assert is_newer("garbage", "1.0.0") is False    # unparseable -> no fake update
    assert is_newer("v2.0.0", "garbage") is False


class _FakeResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_update_available(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: _FakeResp(200, {"tag_name": "v9.9.9"}))
    res = check_for_update("1.2.23")
    assert res["update_available"] is True
    assert res["latest"] == "v9.9.9"
    assert res["error"] is None


def test_up_to_date(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: _FakeResp(200, {"tag_name": "v1.2.23"}))
    res = check_for_update("1.2.23")
    assert res["update_available"] is False
    assert res["error"] is None


def test_no_releases_yet_is_not_an_error(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResp(404))
    res = check_for_update("1.2.23")
    assert res["update_available"] is False
    assert res["error"] == "no_releases"


def test_network_failure_is_data_not_crash(monkeypatch):
    import requests

    def _boom(*a, **k):
        raise ConnectionError("offline")

    monkeypatch.setattr(requests, "get", _boom)
    res = check_for_update("1.2.23", timeout=1)
    assert res["update_available"] is False
    assert res["error"] == "ConnectionError"


def test_disabled_by_env_makes_no_request(monkeypatch):
    import requests

    def _forbidden(*a, **k):
        raise AssertionError("must not hit the network when disabled")

    monkeypatch.setenv("BRANDFORGE_UPDATE_CHECK", "0")
    monkeypatch.setattr(requests, "get", _forbidden)
    res = check_for_update("1.2.23")
    assert res["error"] == "disabled"
    assert res["update_available"] is False


def test_endpoint_returns_cached_state(client):
    r = client.get("/api/update-check")
    assert r.status_code == 200
    data = r.json()
    import server as _srv
    assert data["current"] == _srv.__version__  # was hardcoded — broke on every bump
    assert "update_available" in data


def test_env_gate_defaults_off(monkeypatch):
    # privacy-first default: no env var -> no environment opt-in
    monkeypatch.delenv("BRANDFORGE_UPDATE_CHECK", raising=False)
    assert update_check.enabled() is False


def test_env_opt_in(monkeypatch):
    monkeypatch.setenv("BRANDFORGE_UPDATE_CHECK", "1")
    assert update_check.enabled() is True


def test_consent_flow_gates_update_check(client, monkeypatch):
    import modules.update_check as uc
    monkeypatch.delenv("BRANDFORGE_UPDATE_CHECK", raising=False)  # consent must be the only gate here

    # never asked -> gated, nothing runs
    assert client.get("/api/update-consent").json()["consent"] is None
    assert client.get("/api/update-check").json()["error"] == "consent_required"

    called = []
    def fake_check(*a, **k):
        called.append(1)
        return {"current": "1.2.23", "latest": "v9.9.9", "update_available": True,
                "checked_at": "x", "error": None}
    monkeypatch.setattr(uc, "check_for_update", fake_check)

    # opt in -> the check runs and the result surfaces (reset module cache so
    # this test never depends on threads started by other tests)
    import server as srv
    srv._update_state = {"current": "1.2.23", "latest": None, "update_available": False,
                         "checked_at": None, "error": None}
    srv._update_inflight = False
    assert client.post("/api/update-consent", json={"enabled": True}).json()["consent"] == "on"
    client.get("/api/update-check")
    # Wait for the worker the server just started to actually publish, instead
    # of racing a fixed poll budget — loaded CI runners may schedule the thread
    # late, and a late thread is exactly what used to flake this test.
    worker = srv._update_thread
    assert worker is not None, "opt-in must start the update-check worker"
    worker.join(timeout=60)
    assert not worker.is_alive(), "update-check worker did not finish within 60s"
    got = client.get("/api/update-check").json()
    # Starting the worker is not the same as publishing its result.
    assert called, "opted-in update check must actually run"
    assert got["update_available"] is True

    # opt out -> gated again
    client.post("/api/update-consent", json={"enabled": False})
    assert client.get("/api/update-check").json()["error"] == "consent_required"
