"""Sweep 10: agent-discussion chat, viewable chat images, model picker support.

Covers the three dashboard gaps the founder reported:
1. "swarm agents should discuss with each other in chat" → /api/swarm/chat
2. "if I ask for an image, where does it go?" → /api/files/generated/{name}
   + URL rewriting so the chat answer contains a viewable link
3. "premium models (Claude / Gemini Pro) must be selectable" → provider
   allowlist + model override on /api/settings (engine path covered by
   test_providers_mock.py::test_anthropic_path)
"""
import os

import server  # noqa: F401  (rate-limit store + URL rewriter live here)
from modules.swarm_council import run_council


def test_swarm_chat_returns_discussion(client):
    r = client.post("/api/swarm/chat", json={"message": "Position my coffee brand for remote workers"})
    assert r.status_code == 200, r.text
    d = r.json()
    labels = [t["label"] for t in d["turns"]]
    assert labels == ["Brand Strategist", "Direct-Response Copywriter", "Quality Critic"]
    assert all(t["text"].strip() for t in d["turns"])
    assert d["final"].strip()
    assert d["provider"]  # honest provider label, never missing


def test_swarm_chat_validates_input(client):
    assert client.post("/api/swarm/chat", json={"message": "   "}).status_code == 422
    assert client.post("/api/swarm/chat", json={"message": "x" * 2001}).status_code == 422


def test_swarm_chat_rate_limited(client):
    import os
    os.environ["BRANDFORGE_RATE_SWARM_CHAT"] = "2"
    try:
        server._rate_limit_store.clear()
        assert client.post("/api/swarm/chat", json={"message": "one"}).status_code == 200
        assert client.post("/api/swarm/chat", json={"message": "two"}).status_code == 200
        assert client.post("/api/swarm/chat", json={"message": "three"}).status_code == 429
    finally:
        os.environ["BRANDFORGE_RATE_SWARM_CHAT"] = "100000"
        server._rate_limit_store.clear()


def test_later_agents_read_earlier_turns():
    """The discussion must be a real thread: each agent's prompt contains the
    previous agents' answers (verified by capturing the prompts)."""
    class EchoEngine:
        provider = "offline"
        last_provider = "offline"

        def __init__(self):
            self.prompts = []

        def generate_text(self, prompt, system_prompt=None, max_tokens=2500,
                          use_tools=True, context=None, client_id="default"):
            self.prompts.append(prompt)
            return f"RESPONSE-{len(self.prompts)}"

    eng = EchoEngine()
    result = run_council(eng, "test question")
    texts = [t["text"] for t in result["turns"]]
    assert len(texts) == 3
    # 3 agent turns + 1 final synthesis, all real engine calls
    assert len(eng.prompts) == 4
    # The copywriter's prompt carries the strategist's answer…
    assert "RESPONSE-1" in eng.prompts[1]
    # …the critic's carries both earlier answers…
    assert "RESPONSE-1" in eng.prompts[2] and "RESPONSE-2" in eng.prompts[2]
    # …and the final synthesis sees the whole transcript.
    assert all(f"RESPONSE-{i}" in eng.prompts[3] for i in (1, 2, 3))


def test_generated_image_url_rewrite():
    windows_path = r"Image saved to D:\apps\BrandForgeOS\app\output\ai_image_deadbeef.jpg enjoy"
    out = server._generated_image_urls(windows_path)
    assert "/api/files/generated/ai_image_deadbeef.jpg" in out
    assert "\\" not in out.split("/api/files/generated/")[1].split(" ")[0]

    posix_path = "Saved: /home/user/app/output/ai_image_cafe1234.png"
    assert "/api/files/generated/ai_image_cafe1234.png" in server._generated_image_urls(posix_path)

    plain = "No images here — just text about ai_image_ concepts."
    assert server._generated_image_urls(plain) == plain


def test_generated_file_route(client, tmp_path):
    import server as srv
    _, _, _, tools = srv.get_core()
    name = "ai_image_abcd1234.jpg"
    with open(os.path.join(tools.output_dir, name), "wb") as f:
        f.write(b"\xff\xd8\xff\xe0fakejpeg")

    r = client.get(f"/api/files/generated/{name}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content.startswith(b"\xff\xd8")

    # Traversal / allowlist: everything outside the exact pattern is 404.
    assert client.get("/api/files/generated/..%2Fserver.py").status_code == 404
    assert client.get("/api/files/generated/ai_image_abcd1234.svg").status_code == 404
    assert client.get("/api/files/generated/ai_image_nope9999.jpg").status_code == 404
    assert client.get("/api/files/generated/..%2F..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_settings_exposes_anthropic_and_model_override(client):
    d = client.get("/api/settings").json()
    assert "anthropic" in d["providers"]

    # A premium model can be selected without re-entering a key (the picker
    # flow: user already has a key on file / in env).
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-1234567890"
    try:
        r = client.post("/api/settings", json={"provider": "anthropic", "model": "claude-opus-4-8"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["provider"] == "anthropic"
        assert body["model"] == "claude-opus-4-8"
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        # leave the shared engine in a sane state for later tests
        client.post("/api/settings", json={"provider": "offline"})


def test_http_error_detail_surfaces_provider_reason():
    """The fallback notice must say WHY (invalid key / quota / network),
    not just 'HTTPError' — the black-box notice caused a real support loop."""
    from engines.ai_engine import AIEngine

    class FakeResp:
        status_code = 400
        text = '{"error": {"message": "API key not valid. Please pass a valid API key."}}'

        def json(self):
            import json as _j
            return _j.loads(self.text)

    class FakeHTTPError(Exception):
        response = FakeResp()

    d = AIEngine._http_error_detail(FakeHTTPError("400 Client Error: Bad Request"))
    assert "HTTP 400" in d and "API key not valid" in d

    # quota (openai-style body)
    FakeResp.text = '{"error": {"message": "Resource has been exhausted (quota)"}}'
    FakeResp.status_code = 429
    d = AIEngine._http_error_detail(FakeHTTPError("429 Client Error"))
    assert "HTTP 429" in d and "quota" in d

    # network-level error with no response object
    d = AIEngine._http_error_detail(ConnectionError("getaddrinfo failed"))
    assert "connection failed" in d and "getaddrinfo" not in d


def test_deprecated_models_auto_migrate(tmp_path):
    """A saved config holding a retired model ID (gemini-2.5-flash,
    deepseek-chat, moonshot-v1-8k…) must boot onto the current model instead
    of 404-ing forever — the exact failure the founder hit on 27 Aug 2026."""
    import json
    from engines.ai_engine import AIEngine

    data = tmp_path / "state"
    data.mkdir()
    (data / "config.json").write_text(json.dumps(
        {"provider": "gemini", "model": "gemini-2.0-flash"}))
    eng = AIEngine(provider=None, data_dir=str(data))
    assert eng.model == "gemini-3.6-flash"

    (data / "config.json").write_text(json.dumps(
        {"provider": "deepseek", "model": "deepseek-chat"}))
    eng = AIEngine(provider=None, data_dir=str(data))
    assert eng.model == "deepseek-chat"

    # A genuinely custom model must NOT be touched.
    (data / "config.json").write_text(json.dumps(
        {"provider": "gemini", "model": "my-finetune-v9"}))
    eng = AIEngine(provider=None, data_dir=str(data))
    assert eng.model == "my-finetune-v9"


def test_404_triggers_model_fallback_and_persists(tmp_path):
    """OpenClaw-style primary+fallback: a 404 (retired model) must auto-walk
    the provider's known-good list and PERSIST the working model."""
    import requests
    from engines.ai_engine import AIEngine

    eng = AIEngine(provider="gemini", data_dir=str(tmp_path))
    eng.api_key = "fake-key-123456"
    eng.model = "gemini-9.9-nonexistent"
    seen = []

    def fake_route(prompt, system_prompt, max_tokens, use_tools):
        seen.append(eng.model)
        if eng.model == "gemini-9.9-nonexistent":
            raise requests.HTTPError("404", response=type("R", (), {"status_code": 404})())
        return "recovered via " + eng.model

    eng._route_generate_with_tools = fake_route
    out = eng.generate_text("hello", use_tools=False)
    assert out == "recovered via gemini-3.6-flash", out
    assert seen == ["gemini-9.9-nonexistent", "gemini-3.6-flash"]
    assert eng.config["model"] == "gemini-3.6-flash"  # persisted for next boot


def test_non_404_does_not_walk_fallbacks(tmp_path):
    """A 400 (invalid key) must NOT masquerade as a retired model."""
    import requests
    from engines.ai_engine import AIEngine

    eng = AIEngine(provider="gemini", data_dir=str(tmp_path))
    eng.api_key = "fake-key-123456"
    seen = []

    def fake_route(prompt, system_prompt, max_tokens, use_tools):
        seen.append(eng.model)
        raise requests.HTTPError(
            "400", response=type("R", (), {"status_code": 400, "text": "API key not valid"})())

    eng._route_generate_with_tools = fake_route
    out = eng.generate_text("hello", use_tools=False)
    assert "call failed" in out and "HTTP 400" in out and "API key not valid" in out
    assert len(seen) == 1  # no fallback walk on non-404
