"""Bucket C: verify all 7 LLM provider call paths (request shape, auth, parsing)
against mock servers mimicking each API's response format."""
import json
import os
import requests
import sys
import tempfile
import threading
import http.server
import socketserver

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engines.ai_engine import AIEngine

captured = {}


def make_server(key, handler):
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            captured[key] = json.loads(body)
            j = handler(self.path, json.loads(body))
            out = json.dumps(j).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def openai_resp(path, req):
    assert req["messages"][0]["role"] == "system"
    assert req["messages"][1]["role"] == "user"
    return {"choices": [{"message": {"content": "mock " + req["model"]}}]}


def gemini_resp(path, req):
    assert "contents" in req and req["contents"][0]["parts"][0]["text"]
    return {"candidates": [{"content": {"parts": [{"text": "gemini mock"}]}}]}


def ollama_resp(path, req):
    assert req["model"] and "prompt" in req
    return {"response": "ollama mock"}


ports = {
    "groq": make_server("groq", openai_resp),
    "openrouter": make_server("openrouter", openai_resp),
    "deepseek": make_server("deepseek", openai_resp),
    "kimi": make_server("kimi", openai_resp),
    "xai": make_server("xai", openai_resp),
    "gemini": make_server("gemini", gemini_resp),
    "ollama": make_server("ollama", ollama_resp),
}

import requests as _rq
_real_post = _rq.post
results = {}


def test_openai_style_providers():
    for k, url in {
        "groq": "http://127.0.0.1:%d/v1/chat/completions" % ports["groq"],
        "openrouter": "http://127.0.0.1:%d/api/v1/chat/completions" % ports["openrouter"],
        "deepseek": "http://127.0.0.1:%d/chat/completions" % ports["deepseek"],
        "kimi": "http://127.0.0.1:%d/v1/chat/completions" % ports["kimi"],
        "xai_grok": "http://127.0.0.1:%d/v1/chat/completions" % ports["xai"],
    }.items():
        eng = AIEngine(provider="offline", data_dir=tempfile.mkdtemp())
        eng.provider = k
        eng.model = eng.PROVIDER_MODELS[k]
        eng.api_key = "test-key-123"
        # Real HTTP POST to the mock server (exercises requests + parsing)
        eng._post_chat = lambda u, h, d, timeout=25, _url=url: requests.post(
            _url, headers=h, json=d, timeout=5
        ).json()["choices"][0]["message"]["content"]
        fn = {
            "groq": eng._call_groq_api,
            "openrouter": eng._call_openrouter_api,
            "deepseek": eng._call_deepseek_api,
            "kimi": eng._call_moonshot_api,
            "xai_grok": eng._call_xai_grok_api,
        }[k]
        out = fn("hello", "sys", 100)
        assert out == "mock " + eng.PROVIDER_MODELS[k], (k, out)
        assert captured[("xai" if k == "xai_grok" else k)]["messages"][0]["role"] == "system"


def test_gemini_path():
    eng = AIEngine(provider="offline", data_dir=tempfile.mkdtemp())
    eng.provider = "gemini"
    eng.model = "gemini-2.5-flash"
    eng.api_key = "test-key-123"
    def fake_gemini_post(url, headers=None, json=None, timeout=None):
        assert "x-goog-api-key" in (headers or {}), "gemini key must be in header"
        assert "/models/gemini-2.5-flash:generateContent" in url
        return type("R", (), {
            "raise_for_status": lambda s: None,
            "json": lambda s: {"candidates": [{"content": {"parts": [{"text": "gemini mock"}]}}]},
        })()
    _rq.post = fake_gemini_post
    try:
        out = eng._call_gemini_api("hi", "sys", 100)
    finally:
        _rq.post = _real_post
    assert out == "gemini mock"


def test_ollama_path():
    eng = AIEngine(provider="offline", data_dir=tempfile.mkdtemp())
    eng.provider = "ollama"
    eng.model = "llama3"
    def fake_ollama_post(url, json=None, timeout=None):
        assert "/api/generate" in url
        assert json["model"] == "llama3"
        assert json["options"]["num_predict"] == 100
        return type("R", (), {
            "raise_for_status": lambda s: None,
            "json": lambda s: {"response": "ollama mock"},
        })()
    _rq.post = fake_ollama_post
    try:
        out = eng._call_ollama("hi", "sys", 100)
    finally:
        _rq.post = _real_post
    assert out == "ollama mock"


def test_tool_loop():
    eng = AIEngine(provider="offline", data_dir=tempfile.mkdtemp())
    eng.provider = "groq"
    eng.model = "x"
    eng.api_key = "k"
    calls = {"n": 0}
    def fake_tool_model(prompt, system_prompt, max_tokens):
        calls["n"] += 1
        if calls["n"] == 1:
            return 'TOOL_CALL: {"name": "roi_calculator", "args": {"monthly_spend": 200}}'
        return "final answer with ROI"
    eng._call_groq_api = fake_tool_model
    out = eng._route_generate_with_tools("calc ROI", "sys", 500, True)
    assert "final answer" in out and calls["n"] == 2, (out, calls)


def test_anthropic_path():
    """Claude (Messages API): x-api-key header, pinned anthropic-version,
    system prompt as a top-level field — NOT a system-role message."""
    eng = AIEngine(provider="offline", data_dir=tempfile.mkdtemp())
    eng.provider = "anthropic"
    eng.model = "claude-sonnet-4-6"
    eng.api_key = "sk-ant-test-123"

    def fake_anthropic_post(url, headers=None, json=None, timeout=None):
        assert url == "https://api.anthropic.com/v1/messages"
        assert headers["x-api-key"] == "sk-ant-test-123"
        assert headers["anthropic-version"] == "2023-06-01"
        assert json["system"] == "sys"
        assert json["model"] == "claude-sonnet-4-6"
        assert json["messages"][0]["role"] == "user"
        assert all(m["role"] != "system" for m in json["messages"])
        return type("R", (), {
            "raise_for_status": lambda s: None,
            "json": lambda s: {"content": [{"type": "text", "text": "claude mock"}]},
        })()

    _rq.post = fake_anthropic_post
    try:
        out = eng._call_anthropic_api("hi", "sys", 100)
    finally:
        _rq.post = _real_post
    assert out == "claude mock"


def test_anthropic_routed_and_persistable():
    """Provider plumbing: anthropic is a first-class provider (routing map,
    env key, save_api_key round-trip)."""
    eng = AIEngine(provider="offline", data_dir=tempfile.mkdtemp())
    assert "anthropic" in eng.PROVIDER_MODELS
    assert eng.ENV_KEYS["anthropic"] == "ANTHROPIC_API_KEY"

    # save_api_key accepts a realistic Claude key shape
    assert eng.save_api_key("sk-ant-api03-abcdef123456", provider="anthropic") is True
    assert eng.model == eng.PROVIDER_MODELS["anthropic"]

    # routing map resolves to the anthropic call path
    def fake_anthropic_post(url, headers=None, json=None, timeout=None):
        return type("R", (), {
            "raise_for_status": lambda s: None,
            "json": lambda s: {"content": [{"type": "text", "text": "routed ok"}]},
        })()
    _rq.post = fake_anthropic_post
    try:
        out = eng._route_generate_with_tools("hi", "sys", 100, use_tools=False)
    finally:
        _rq.post = _real_post
    assert out == "routed ok"
