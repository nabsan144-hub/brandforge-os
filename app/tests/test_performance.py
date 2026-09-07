"""Phase 6 (§6.1): manual ROI/performance loop."""
import tempfile

import pytest

from modules.performance_tracker import PerformanceTracker


def _tracker():
    return PerformanceTracker(tempfile.mkdtemp(prefix="perf_test_"))


def test_summary_math():
    tr = _tracker()
    tr.add_entry("c1", spend=100, clicks=200, leads=10, revenue=400)
    tr.add_entry("c1", spend=100, clicks=200, leads=10, revenue=100)
    s = tr.summary("c1")
    assert s["entries"] == 2
    assert s["spend"] == 200 and s["revenue"] == 500
    assert s["profit"] == 300
    assert s["cpc"] == 0.5
    assert s["cpl"] == 10
    assert s["roas"] == 2.5
    assert s["roi_pct"] == 150.0


def test_zero_spend_no_division_by_zero():
    tr = _tracker()
    tr.add_entry("c1", spend=0, clicks=0, leads=0, revenue=0)
    s = tr.summary("c1")
    assert s["cpc"] is None and s["cpl"] is None
    assert s["roas"] is None and s["roi_pct"] is None


def test_campaigns_are_isolated():
    tr = _tracker()
    tr.add_entry("a", spend=10, revenue=20)
    tr.add_entry("b", spend=5, revenue=5)
    assert tr.summary("a")["profit"] == 10
    assert tr.summary("b")["profit"] == 0


def test_validation_rejects_negative_and_huge():
    tr = _tracker()
    with pytest.raises(ValueError):
        tr.add_entry("c", spend=-1)
    with pytest.raises(ValueError):
        tr.add_entry("c", spend=10_000_001)
    with pytest.raises(ValueError):
        tr.add_entry("c", spend="not-a-number")


def test_api_performance_roundtrip(client):
    r = client.post("/api/swarm/run", json={
        "campaign_name": "Perf Loop", "product_name": "Loop Tea",
        "industry": "Retail", "target_audience": "Tea people",
        "key_benefits": "Calm"})
    assert r.status_code == 200
    name = r.json()["campaign_name"]

    post = client.post(f"/api/campaigns/{name}/performance", json={
        "spend": 50, "clicks": 100, "leads": 5, "revenue": 250,
        "note": "week 1"})
    assert post.status_code == 200, post.text
    assert post.json()["summary"]["roas"] == 5.0

    got = client.get(f"/api/campaigns/{name}/performance").json()
    assert got["entries"][0]["note"] == "week 1"
    assert got["summary"]["profit"] == 200
    # AI side of the loop rides along
    assert got["provider"] == "offline"
    assert got["quality"] is None or isinstance(got["quality"], dict)


def test_api_performance_unknown_campaign_404(client):
    r = client.post("/api/campaigns/nope/performance", json={"spend": 1})
    assert r.status_code == 404
    assert client.get("/api/campaigns/nope/performance").status_code == 404


def test_api_performance_rejects_negative(client):
    r = client.post("/api/swarm/run", json={
        "campaign_name": "Perf Neg", "product_name": "Neg Tea",
        "industry": "Retail", "target_audience": "x", "key_benefits": "y"})
    name = r.json()["campaign_name"]
    bad = client.post(f"/api/campaigns/{name}/performance", json={"spend": -5})
    assert bad.status_code == 422
