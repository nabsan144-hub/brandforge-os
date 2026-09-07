"""Regression tests for the final desktop hardening pass."""

import logging
import tempfile

import pytest
from pydantic import ValidationError


def test_openrouter_model_ids_are_allowed_but_path_traversal_is_not():
    from server import SettingsRequest

    assert SettingsRequest(provider="openrouter", model="deepseek/deepseek-r1:free").model == "deepseek/deepseek-r1:free"
    with pytest.raises(ValidationError):
        SettingsRequest(provider="openrouter", model="../../etc/passwd")


def test_settings_key_status_reports_each_provider(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_provider_key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.get("/api/settings/key-status?provider=groq").json()["has_api_key"] is True
    assert client.get("/api/settings/key-status?provider=gemini").json()["has_api_key"] is False
    assert client.get("/api/settings/key-status?provider=not-a-provider").status_code == 400


def test_ollama_failure_falls_back_with_context_and_honest_provider(tmp_path, monkeypatch):
    from engines.ai_engine import get_engine

    engine = get_engine(provider="ollama", data_dir=str(tmp_path))

    def unavailable(*args, **kwargs):
        raise RuntimeError("Ollama unavailable")

    monkeypatch.setattr(engine, "_call_ollama", unavailable)
    result = engine.generate_text(
        "campaign brief", use_tools=False,
        context={"agent": "strategist", "product": "Acme Coffee"},
    )
    assert "Acme Coffee" in result
    assert engine.last_provider == "offline"
    assert engine.generate_with_tools("hello", tools_to_use=[])["provider"] == "offline"


def test_long_campaign_name_gets_a_finite_revision_name(tmp_path):
    from modules.project_manager import ProjectManager

    manager = ProjectManager(base_dir=str(tmp_path))
    name = "x" * 60
    manager.save_campaign(name, {"product_name": "P", "strategy_text": "S"}, {"copy_text": "C"}, {})
    result = manager.create_revision(name)
    assert result["name"].endswith("_v2")
    assert len(result["name"]) <= 60


def test_comment_only_approval_is_visible(client):
    created = client.post("/api/swarm/run", json={
        "campaign_name": "Comment-only approval",
        "product_name": "Product",
        "industry": "Retail",
        "target_audience": "Customers",
        "key_benefits": "Clear price",
    })
    assert created.status_code == 200
    name = created.json()["campaign_name"]
    token = client.post(f"/api/campaigns/{name}/approval-links").json()["token"]
    response = client.put(f"/api/approvals/{token}", json={"comment": "Reviewed; please confirm the price."})
    assert response.status_code == 200
    assert response.json()["approval"]["decision"] == "commented"
    assert client.put(f"/api/approvals/{token}", json={"decision": ""}).status_code == 422


def test_offline_swarm_does_not_attempt_live_search(monkeypatch):
    from engines.ai_engine import get_engine
    from modules.swarm_director import SwarmDirector

    engine = get_engine(provider="offline", data_dir=tempfile.mkdtemp(prefix="vg_offline_search_"))

    def fail(*args, **kwargs):
        raise AssertionError("offline swarm attempted a network search")

    monkeypatch.setattr(engine.searcher, "search", fail)
    result = SwarmDirector(engine).execute_swarm_campaign("P", "I", "A", "B")
    assert result["meta"]["research_live"] is False
    assert "unavailable" in result["strategy_data"]["market_research"].lower()


def test_swarm_scopes_every_agent_chat_to_campaign_client(tmp_path, monkeypatch):
    from engines.ai_engine import get_engine
    from modules.swarm_director import SwarmDirector

    engine = get_engine(provider="offline", data_dir=str(tmp_path))
    calls = []
    original = engine.generate_text

    def wrapped(prompt, *args, **kwargs):
        calls.append(kwargs.get("client_id"))
        return original(prompt, *args, **kwargs)

    monkeypatch.setattr(engine, "generate_text", wrapped)
    SwarmDirector(engine).execute_swarm_campaign("Product", "Retail", "Buyers", "Useful", client_id="agency_client")
    assert calls and all(client_id == "agency_client" for client_id in calls)


def test_rate_limit_store_is_bounded(client):
    import server

    server._rate_limit_store.clear()
    old_cap = server._RATE_STORE_CAP
    server._RATE_STORE_CAP = 100
    try:
        for i in range(250):
            assert server._check_rate_limit(f"198.51.100.{i}", limit=1, bucket="hard-cap")
        assert len(server._rate_limit_store) <= 100
    finally:
        server._RATE_STORE_CAP = old_cap


def test_ddg_zero_result_response_is_logged(caplog):
    from modules.web_searcher import WebSearcher

    class Response:
        status_code = 200
        text = "<html><body>layout changed</body></html>"

        def raise_for_status(self):
            return None

    searcher = WebSearcher()
    searcher.session = type("Session", (), {"post": lambda self, *a, **k: Response()})()
    with caplog.at_level(logging.WARNING, logger="brandforge.web_searcher"):
        assert searcher._search_ddg_html("query", 3) == []
    assert "found 0 results" in caplog.text
