"""Regression tests for the 2026-08-26 two-pass audit fixes.

Each test pins one previously-verified bug so it cannot silently return:
- tools respect the engine/tool data_dir (tenant isolation)
- memory search/save are client-scoped
- Settings model validation rejects path-injectable values
- swarm branding follows the campaign's client_id, not the active client
"""
import tempfile

import pytest

from fastapi.testclient import TestClient
from server import app as server_app
from modules.client_manager import ClientManager
from modules.mcp_registry import MCPRegistry
from modules.memory_manager import MemoryManager
from modules.project_manager import ProjectManager


@pytest.fixture()
def client():
    with TestClient(server_app) as c:
        yield c


def _tenant_dir(prefix="vg_fix_") -> str:
    return tempfile.mkdtemp(prefix=prefix)


# ---- M4: tool registry must use ITS data dir (not the app-level one) ----

def test_list_campaigns_tool_uses_registry_data_dir():
    tenant = _tenant_dir()
    pm = ProjectManager(base_dir=tenant)
    pm.save_campaign(
        "TenantCampaign", {"product_name": "X", "industry": "I",
                           "target_audience": "A", "strategy_text": "S"},
        {"copy_text": "C"}, {"hero.svg": "<svg/>"}, client_id="c1")

    reg = MCPRegistry(base_dir=tenant)
    res = reg.execute_tool("list_campaigns", {})
    names = [c.get("name") for c in res if isinstance(c, dict)]
    assert "tenantcampaign" in names, (
        "list_campaigns must read the registry's own data dir, not the "
        "app-level default (cross-tenant reads in hosted mode)")


def test_search_memory_tool_uses_registry_data_dir_and_client():
    tenant = _tenant_dir()
    mm = MemoryManager(base_dir=tenant)
    cm = ClientManager(base_dir=tenant)
    mm.add_chat("user", "exclusive client-a pricing 12345", client_id="client_a")
    cm.save_client({"client_id": "client_a", "client_name": "A"})
    cm.set_active_client("client_a")

    reg = MCPRegistry(base_dir=tenant)
    res = reg.execute_tool("search_memory", {"query": "pricing 12345"})
    assert any("client-a pricing" in str(r) for r in res), (
        "search_memory must search the registry's own memory DB")


# ---- M8/M9: memory client scoping ----

def test_search_history_is_client_scoped():
    tenant = _tenant_dir()
    mm = MemoryManager(base_dir=tenant)
    mm.add_chat("user", "client-a secret pricing 999", client_id="client_a")
    mm.add_chat("user", "client-b lunch plans only", client_id="client_b")

    hits_a = mm.search_history("secret pricing", limit=5, client_id="client_a")
    assert any("client-a" in str(r) for r in hits_a)

    hits_b = mm.search_history("secret pricing", limit=5, client_id="client_b")
    assert not any("client-a" in str(r) for r in hits_b), (
        "one client's chats must never surface in another client's search")


def test_save_long_term_is_client_scoped():
    tenant = _tenant_dir()
    mm = MemoryManager(base_dir=tenant)
    mm.save_long_term("deal", "client-a deal details", client_id="client_a")
    mm.save_long_term("deal", "client-b deal details", client_id="client_b")

    assert "client-a deal details" in mm.get_long_term_memory(client_id="client_a")
    assert "client-a deal details" not in mm.get_long_term_memory(client_id="client_b")


# ---- M24: model name validation ----

def test_settings_model_validation_rejects_url_unsafe_chars():
    # a model name must not be able to inject into the Gemini URL path
    from server import SettingsRequest
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        SettingsRequest(provider="gemini", model="/../../etc/passwd")
    ok = SettingsRequest(provider="gemini", model="gemini-2.5-flash")
    assert ok.model == "gemini-2.5-flash"


# ---- M29: swarm branding follows the campaign's client_id ----

def test_swarm_uses_campaign_client_branding():
    from modules.swarm_director import SwarmDirector

    class FakeClients:
        profiles = {
            "brand_a": {"client_id": "brand_a", "client_name": "A",
                        "primary_color": "#111111", "secondary_color": "#222222",
                        "agency_brand": "BRAND A", "brand_promise": "",
                        "proof_points": "", "prohibited_claims": "",
                        "tone_of_voice": "Direct", "agency_footer": "",
                        "show_brandforge_branding": True},
            "brand_b": {"client_id": "brand_b", "client_name": "B",
                        "primary_color": "#AAAAAA", "secondary_color": "#BBBBBB",
                        "agency_brand": "BRAND B", "brand_promise": "",
                        "proof_points": "", "prohibited_claims": "",
                        "tone_of_voice": "Direct", "agency_footer": "",
                        "show_brandforge_branding": True},
        }

        def get_client(self, cid):
            return self.profiles.get(cid)

        def get_active_client(self):
            return self.profiles["brand_a"]

    class FakeEngine:
        provider = "offline"
        clients = FakeClients()
        searcher = None
        memory = None

        def generate_text(self, *a, **kw):
            return "strategy output"

    eng = FakeEngine()
    swarm = SwarmDirector(eng)
    result = swarm.execute_swarm_campaign(
        "Product", "Retail", "Audience", "Quality, value", client_id="brand_b")
    strat = result["strategy_data"]
    assert strat["agency_brand"] == "BRAND B", (
        "campaign branded with the ACTIVE client instead of the campaign's "
        "own client_id")
    assert strat["color_palette"][0]["hex"] == "#AAAAAA"


# ---- Phase 2 (§2.3): vector-response length mismatch must not corrupt results ----

def test_search_history_mismatched_vector_response_falls_back_not_truncated():
    """A vector DB returning 2 documents but 1 metadata must not silently
    zip-truncate into misaligned {message, metadata} pairs — the search has
    to fall through to the SQLite LIKE path instead."""
    tenant = _tenant_dir()
    mm = MemoryManager(base_dir=tenant)
    mm.add_chat("user", "mismatch fallback probe 777", client_id="client_a")

    class _MismatchedVectorDB:
        def query(self, **kwargs):
            return {
                "documents": [["ghost one", "ghost two"]],   # 2 docs...
                "metadatas": [[{"role": "user"}]],           # ...but 1 meta
            }

    mm.vector_db = _MismatchedVectorDB()
    results = mm.search_history("fallback probe 777", limit=5, client_id="client_a")

    assert results, "search must still return the SQLite fallback hits"
    assert all("message" in r and "role" in r for r in results), (
        "results must come from the SQLite path (timestamp/role/message shape), "
        "not from misaligned vector pairs")
    assert any("fallback probe 777" in str(r.get("message", "")) for r in results)
    assert not any("ghost" in str(r) for r in results), (
        "truncated/misaligned vector documents must never surface")
