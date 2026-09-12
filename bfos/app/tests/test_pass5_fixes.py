"""Regression tests for the fifth full-codebase audit pass (2026-08-26).

Pins the shared-state concurrency + public-endpoint-abuse fixes:
- approval updates are atomic (no lost updates under threads)
- approval comments are capped; token store is bounded
- public approval portal POST is rate-limited
- long-term memory appends are atomic under concurrency
"""
import tempfile
import threading

import pytest

from fastapi.testclient import TestClient
from server import app as server_app


@pytest.fixture()
def client():
    with TestClient(server_app) as c:
        c.headers["X-BrandForge-Token"] = c.get("/api/session").json()["capability"]
        yield c


# ---- ApprovalManager: thread safety + bounds ----
def test_approval_updates_are_atomic():
    from modules.approval_manager import ApprovalManager
    am = ApprovalManager(tempfile.mkdtemp(prefix="vg_appr_"))
    token = am.create("Campaign")
    results = []
    def worker(i):
        results.append(am.update(token, comment=f"comment-{i}") is not None)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert all(results)
    item = am.get(token)
    texts = [c["text"] for c in item["comments"]]
    assert len(set(texts)) == 20, f"lost updates under concurrency: {len(set(texts))}/20"


def test_approval_comments_are_capped():
    from modules.approval_manager import ApprovalManager, MAX_COMMENTS_PER_TOKEN
    am = ApprovalManager(tempfile.mkdtemp(prefix="vg_appr2_"))
    token = am.create("Campaign")
    for i in range(MAX_COMMENTS_PER_TOKEN + 10):
        am.update(token, comment=f"c{i}")
    item = am.get(token)
    assert len(item["comments"]) == MAX_COMMENTS_PER_TOKEN, (
        "comment store must be capped so a public link can't balloon the file")


def test_approval_token_store_is_bounded(monkeypatch):
    import modules.approval_manager as amod
    # Use a small bound so the O(n^2) JSON-dump test stays fast
    monkeypatch.setattr(amod, "MAX_TOKENS", 20)
    am = amod.ApprovalManager(tempfile.mkdtemp(prefix="vg_appr3_"))
    for i in range(45):
        am.create(f"Campaign{i}")
    with open(am.path, encoding="utf-8") as f:
        import json
        d = json.load(f)
    assert len(d) <= 20, "token store must be bounded (oldest evicted)"
    # the newest token must still exist (eviction removes oldest, not newest);
    # campaign names are stored lowercased by safe_slug
    newest = am._load()
    assert any("campaign44" in v.get("campaign", "") for v in newest.values())


def test_approval_portal_post_rate_limited(client, monkeypatch):
    # create a campaign + approval link to hit the public portal
    r = client.post("/api/swarm/run", json={
        "campaign_name": "RatePortal", "product_name": "P", "industry": "G",
        "target_audience": "A", "key_benefits": "b"})
    assert r.status_code == 200, r.text[:120]
    name = r.json()["campaign_name"]
    tok = client.post(f"/api/campaigns/{name}/approval-links").json()["token"]

    monkeypatch.setenv("BRANDFORGE_RATE_APPR_POST", "3")
    statuses = []
    for _ in range(4):
        statuses.append(client.post(f"/approval/{tok}", data={
            "decision": "approved", "comment": "ok"}).status_code)
    assert statuses[:3] == [200, 200, 200], statuses
    assert statuses[3] == 429, f"4th portal post must be rate-limited, got {statuses}"


# ---- MemoryManager: long-term appends are atomic ----
def test_long_term_memory_concurrent_appends_no_loss():
    from modules.memory_manager import MemoryManager
    mm = MemoryManager(base_dir=tempfile.mkdtemp(prefix="vg_mem_"))
    def worker(i):
        mm.save_long_term(f"key{i}", f"value-{i}")
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    content = mm.get_long_term_memory()
    for i in range(10):
        assert f"value-{i}" in content, f"concurrent long-term save lost value-{i}"
