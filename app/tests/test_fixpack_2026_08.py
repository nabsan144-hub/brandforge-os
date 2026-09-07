"""Fix-pack regression tests (2026-08-26 audit, v1.2.22).

Each test pins one confirmed bug from the independent audit so it can never
silently return:

- H1  provider switch must not persist another provider's model
- H2  re-running a campaign name must NOT destroy the saved campaign
- H3  swarm prompts must not be truncated at 2,000 chars
- H4  binary deliverables (hero_image.jpg) are reported in campaign files
- M1  WebSocket chat saves under the ACTIVE client, with client context
- M2  corrupt campaign.json -> clean 422, not a 500 traceback
- M3  logo GET endpoint serves uploads; rejects paths outside the logos dir
- L8  /api/memory defaults to the active client
- L1  CSP hash is computed from the actual dist index.html
"""

import io
import json
import os
import zipfile



def _make_campaign(client, name, product="Apex Coffee"):
    r = client.post("/api/swarm/run", json={
        "campaign_name": name, "product_name": product, "industry": "Retail",
        "target_audience": "Remote workers", "key_benefits": "Fresh, fast"})
    assert r.status_code == 200, r.text
    return r.json()["campaign_name"]


# ---------- H1: model must follow the provider ----------

def test_settings_rejects_foreign_default_model(client):
    # Configure gemini with a key, then switch to groq while the form still
    # carries gemini's default model — the engine must NOT keep it.
    r = client.post("/api/settings", json={
        "provider": "gemini", "api_key": "fake-gemini-key-123456"})
    assert r.status_code == 200, r.text

    r = client.post("/api/settings", json={
        "provider": "groq", "api_key": "fake-groq-key-123456",
        "model": "gemini-2.5-flash"})  # stale model from the other provider
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == "groq"
    assert r.json()["model"] == "qwen/qwen3.8-27b", r.json()["model"]


def test_settings_rejects_offline_engine_internal_model(client):
    client.post("/api/settings", json={
        "provider": "groq", "api_key": "fake-groq-key-123456",
        "model": "smart-offline-engine-v2"})
    r = client.get("/api/settings").json()
    assert r["provider"] == "groq"
    assert r["model"] == "qwen/qwen3.8-27b", r["model"]


def test_settings_keeps_custom_model(client):
    # A legit custom model name for the same provider must pass through.
    r = client.post("/api/settings", json={
        "provider": "groq", "api_key": "fake-groq-key-123456",
        "model": "qwen/qwen3.6-27b"})  # live catalog model, not the default
    assert r.status_code == 200, r.text
    assert r.json()["model"] == "qwen/qwen3.6-27b"


def test_settings_get_hides_offline_internal_model(client):
    client.post("/api/settings", json={"provider": "offline"})
    r = client.get("/api/settings").json()
    assert r["provider"] == "offline"
    assert r["model"] == "", "offline engine's internal name must not leak"


# ---------- H2: re-run must not destroy the saved campaign ----------

def test_swarm_rerun_auto_revisions_and_preserves_history(client):
    first = _make_campaign(client, "Rerun guard", product="Apex Coffee")
    assert first == "rerun_guard"

    # approve the first campaign, then re-run the SAME name
    r = client.put(f"/api/campaigns/{first}/status", json={"status": "approved"})
    assert r.status_code == 200

    second = _make_campaign(client, "Rerun guard", product="Apex Coffee v2")
    assert second == "rerun_guard_v2", second

    original = client.get(f"/api/campaigns/{first}").json()
    assert original["status"] == "approved", "re-run reset the status (data loss)"
    assert len(original["status_history"]) >= 2
    assert original["strategy"]["product_name"] == "Apex Coffee"
    assert original["revision_number"] == 1

    revised = client.get(f"/api/campaigns/{second}").json()
    assert revised["status"] == "draft"
    assert revised["revision_number"] == 2
    assert revised["revision_of"] == "rerun_guard"
    assert revised["strategy"]["product_name"] == "Apex Coffee v2"

    # third run with the same name keeps counting
    third = _make_campaign(client, "Rerun guard")
    assert third == "rerun_guard_v3", third


def test_swarm_rerun_response_points_at_the_real_campaign(client):
    _make_campaign(client, "Pointer camp")  # side effect: creates the campaign
    again = client.post("/api/swarm/run", json={
        "campaign_name": "Pointer camp", "product_name": "P2", "industry": "i",
        "target_audience": "a", "key_benefits": "b"})
    body = again.json()
    assert body["campaign_name"] == "pointer_camp_v2"
    # view/download URLs must reference the folder that actually exists
    assert client.get(body["view"]).status_code == 200
    assert client.get(body["download"]).status_code == 200


# ---------- H3: prompt ceiling ----------

def test_long_prompts_are_not_truncated(tmp_path):
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline", data_dir=str(tmp_path))
    captured = {}

    def fake_offline(prompt, context):
        captured["prompt"] = prompt
        captured["context"] = context
        return "ok"

    eng._offline_smart_generate = fake_offline
    long_prompt = "x" * 3000 + " FINAL-TASK-INSTRUCTIONS"
    eng.generate_text(long_prompt)
    assert captured["prompt"].endswith("FINAL-TASK-INSTRUCTIONS"), \
        "task instructions at the tail were truncated"
    assert len(captured["prompt"]) == len(long_prompt)


def test_extract_context_does_not_mutate_caller_dict(tmp_path):
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline", data_dir=str(tmp_path))
    caller_ctx = {"product": "StructuredProduct", "agent": "strategist"}
    eng._offline_smart_generate = lambda p, c: "ok"
    eng.generate_text("Campaign — Product: PromptProduct, Industry: Retail",
                      context=caller_ctx)
    assert caller_ctx == {"product": "StructuredProduct", "agent": "strategist"}, \
        "caller's context dict was mutated in place"


# ---------- H4: binary deliverables are listed ----------

def test_binary_deliverable_is_listed_and_openable(client):
    name = _make_campaign(client, "Binary visual")
    import modules.project_manager as pm_mod
    detail = client.get(f"/api/campaigns/{name}").json()
    # simulate an AI image deliverable (bytes) in the folder
    pm = pm_mod.ProjectManager()
    path = pm.get_campaign_file(name, "hero_banner.svg")
    with open(os.path.join(os.path.dirname(path), "hero_image.jpg"), "wb") as f:
        f.write(b"\xff\xd8FAKEJPGDATA\xff\xd9")

    detail = client.get(f"/api/campaigns/{name}").json()
    entry = next((f for f in detail["files"] if f["name"] == "hero_image.jpg"), None)
    assert entry is not None, "binary deliverable missing from file list"
    assert "content" not in entry  # binary: no text content — the UI must
    # guard on existence (hasFile), not text content
    r = client.get(f"/api/campaigns/{name}/files/hero_image.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    assert r.content.startswith(b"\xff\xd8")


# ---------- M1: WebSocket uses the active client ----------

def test_websocket_chat_uses_active_client_context(client):
    active = client.get("/api/clients").json()["active"]
    active_id = active["client_id"]

    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "connected"
        ws.send_text("hello from the websocket")
        reply = ws.receive_json()
        assert reply["type"] == "response"

    # the WS conversation must land under the ACTIVE client (not "default")
    r = client.get(f"/api/memory?limit=10&client={active_id}")
    messages = [m["message"] for m in r.json()["history"]]
    assert any("hello from the websocket" in m for m in messages), \
        "WS chat was saved under a different client bucket than REST chat"


# ---------- M2: corrupt campaign.json -> clean error ----------

def test_corrupt_campaign_json_returns_422_not_500(client, tmp_path):
    name = _make_campaign(client, "Corrupt json")
    import modules.project_manager as pm_mod
    pm = pm_mod.ProjectManager()
    path = os.path.join(pm._campaign_path(name), "campaign.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"campaign_name": "truncated...')  # half-written file

    r = client.post(f"/api/campaigns/{name}/revisions")
    assert r.status_code == 422, f"expected clean 422, got {r.status_code}"
    # status update maps the JSON error onto its existing ValueError -> 400
    r2 = client.put(f"/api/campaigns/{name}/status", json={"status": "approved"})
    assert r2.status_code in (400, 422), r2.status_code


def test_campaign_json_written_atomically(client, tmp_path, monkeypatch):
    # save_campaign must leave no campaign.json.tmp behind and the final
    # file must be complete JSON (tmp + os.replace, not direct write).
    name = _make_campaign(client, "Atomic write")
    import modules.project_manager as pm_mod
    pm = pm_mod.ProjectManager()
    folder = pm._campaign_path(name)
    assert not os.path.exists(os.path.join(folder, "campaign.json.tmp"))
    with open(os.path.join(folder, "campaign.json"), encoding="utf-8") as f:
        data = json.load(f)  # complete, parseable
    assert data["campaign_name"] == name


# ---------- M3: logo GET endpoint ----------

def _png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 200, 50)).save(buf, format="PNG")
    return buf.getvalue()


def test_logo_roundtrip_and_path_guard(client, tmp_path, monkeypatch):
    clients = client.get("/api/clients").json()["clients"]
    cid = clients[0]["client_id"]

    r = client.post(f"/api/clients/{cid}/logo",
                    files={"logo": ("mark.png", _png_bytes(), "image/png")})
    assert r.status_code == 200, r.text

    served = client.get(f"/api/clients/{cid}/logo")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content[:8] == b"\x89PNG\r\n\x1a\n"

    # a hand-edited profile pointing logo_path outside the logos dir -> 404
    import modules.client_manager as cm_mod
    cm = cm_mod.ClientManager()
    profile = cm.get_client(cid)
    profile["logo_path"] = os.path.join(os.path.dirname(cm.clients_dir), "config.json")
    cm.save_client(profile)
    assert client.get(f"/api/clients/{cid}/logo").status_code == 404

    # client without a logo -> 404
    assert client.get("/api/clients/nonexistent_client/logo").status_code == 404


# ---------- L8: /api/memory defaults to the active client ----------

def test_memory_defaults_to_active_client(client):
    r = client.post("/api/chat", json={"message": "memory default probe"})
    assert r.status_code == 200
    default_view = client.get("/api/memory?limit=50").json()
    assert default_view["count"] > 0, \
        "default /api/memory returned empty — it must target the active client"
    msgs = [m["message"] for m in default_view["history"]]
    assert any("memory default probe" in m for m in msgs)


# ---------- L1: CSP hash computed from the real dist ----------

def test_csp_uses_hash_of_actual_dist_script():
    import server
    import re as _re
    import base64 as _b64
    import hashlib as _hl
    dist = os.path.join(os.path.dirname(server.__file__), "web", "dist", "index.html")
    if not os.path.exists(dist):
        return  # pip-style install without static assets: fallback constant
    with open(dist, encoding="utf-8") as f:
        html = f.read()
    m = _re.search(r"<script>(.*?)</script>", html, _re.DOTALL)
    assert m, "expected the inline theme script in dist/index.html"
    expected = "sha256-" + _b64.b64encode(_hl.sha256(m.group(1).encode()).digest()).decode()
    assert expected in server._DEFAULT_CSP, \
        "CSP must carry the hash of the ACTUAL dist inline script"


# ---------- ZIP export sanity (auto-revision interacts with exports) ----------

def test_zip_download_of_revision(client):
    _make_campaign(client, "Zip revision")  # side effect: v1 of the pair
    second = _make_campaign(client, "Zip revision")
    assert second == "zip_revision_v2"
    r = client.get(f"/api/campaigns/{second}/download")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
    assert "campaign.json" in names
    assert any(n.endswith("hero_banner.svg") for n in names)


# ---- Phase 4 (§4.1): trust signals must arrive AT generation completion ----

def test_swarm_response_carries_quality_and_provider(client):
    r = client.post("/api/swarm/run", json={
        "campaign_name": "Trust signals", "product_name": "Signal Tea",
        "industry": "Retail", "target_audience": "Remote workers",
        "key_benefits": "Calm, honest"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["provider"] == "offline", "offline engine must label itself"
    q = data["quality"]
    assert isinstance(q["score"], int) and 0 <= q["score"] <= 100
    assert q["status"] in ("ready_for_internal_review", "needs_revision")
    assert data["claim_review"]["warning_count"] >= 0
    assert isinstance(data["claim_review"]["warnings"], list)
