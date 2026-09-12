"""Stage 0 — FREEZE & CHARACTERIZE.

Golden-file contract for the offline engine + structural contract for
campaign.json. These exist so that ANY future change which alters existing
user-visible output fails instantly instead of silently regressing.

If you intentionally improve the engine output, update the golden files in
tests/golden/ IN THE SAME COMMIT as the change (and say so in the CHANGELOG).
"""
import os
import tempfile

import pytest

GOLDEN = os.path.join(os.path.dirname(__file__), "golden")


def _engine():
    from engines.ai_engine import AIEngine
    return AIEngine(provider="offline", data_dir=tempfile.mkdtemp())


def _golden(name):
    with open(os.path.join(GOLDEN, name), encoding="utf-8") as f:
        return f.read()


CTX = {
    "product": "Apex Coffee",
    "industry": "Specialty Coffee",
    "target_audience": "Busy professionals",
    "key_benefits": "Organic beans, same-day delivery",
}


@pytest.mark.parametrize("agent,file", [
    ("strategist", "offline_strategy.txt"),
    ("copywriter", "offline_copy.txt"),
])
def test_offline_agent_output_matches_golden(agent, file):
    eng = _engine()
    out = eng._offline_smart_generate("Deliver the engagement output.",
                                      {**CTX, "agent": agent})
    assert out == _golden(file), (
        f"offline engine output changed for agent={agent}. If intentional, "
        f"update tests/golden/{file} in the same commit.")


def test_offline_roi_matches_golden():
    eng = _engine()
    out = eng._offline_smart_generate("ROI calculator: I pay $200/month for tools", {})
    assert out == _golden("offline_roi.txt")


def test_offline_generic_matches_golden():
    eng = _engine()
    out = eng._offline_smart_generate("hello", {})
    assert out == _golden("offline_generic.txt")


def test_swarm_campaign_json_schema_contract(client):
    """campaign.json must keep its exact public shape — keys, types, and the
    offline strategy/copy text pinned by the golden files."""
    r = client.post("/api/swarm/run", json={
        "campaign_name": "Schema Contract", "product_name": CTX["product"],
        "industry": CTX["industry"], "target_audience": CTX["target_audience"],
        "key_benefits": CTX["key_benefits"]})
    assert r.status_code == 200, r.text[:200]
    name = r.json()["campaign_name"]

    detail = client.get(f"/api/campaigns/{name}").json()
    # structural contract
    for key in ("campaign_name", "client_id", "provider", "research_live",
                "strategy", "copy", "analysis", "visuals", "status",
                "revision_number", "status_history", "created"):
        assert key in detail, f"campaign.json missing {key}"
    assert isinstance(detail["strategy"], dict)
    assert isinstance(detail["copy"], dict)
    assert isinstance(detail["analysis"], dict)
    assert isinstance(detail["visuals"], list)
    assert isinstance(detail["status_history"], list)
    assert detail["status"] == "draft"
    assert detail["revision_number"] == 1
    assert detail["research_live"] in (True, False)
    assert detail["provider"] in ("offline", "ollama", "groq", "gemini")

    # the offline swarm must produce exactly the golden strategy + copy
    strat_text = detail["strategy"]["strategy_text"]
    copy_text = detail["copy"]["copy_text"]
    # strategy contains the golden positioning sentence, copy contains golden hook
    assert "Apex Coffee is a Specialty Coffee choice" in strat_text
    assert "Looking for Organic beans? Meet Apex Coffee." in copy_text
    assert "Welcome Email" in copy_text and "Hero Headline" in copy_text

    # visuals are the known deliverable set
    assert "hero_banner.svg" in detail["visuals"]
    assert "instagram_square.svg" in detail["visuals"]
    assert "ad_card.html" in detail["visuals"]
