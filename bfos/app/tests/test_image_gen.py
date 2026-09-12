"""AI image generation: honesty rules + binary deliverable handling."""

import os


def test_offline_swarm_never_calls_image_api(monkeypatch):
    """Offline/Ollama keep the zero-outbound promise: the Pollinations API
    must not be touched, and no hero_image.jpg may appear."""
    import modules.image_generator as ig
    import modules.swarm_director as sd

    def _boom(*a, **kw):
        raise AssertionError("image API called in offline mode!")

    monkeypatch.setattr(ig, "generate_image_bytes", _boom)
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    swarm = sd.SwarmDirector(eng)
    result = swarm.execute_swarm_campaign("Probe", "Test", "aud", "a, b")
    assert "hero_image.jpg" not in result["visual_files"]
    assert result["meta"]["ai_image"] is False


def test_allow_ai_image_false_blocks_generation(monkeypatch):
    """Hosted plan quotas gate images via allow_ai_image=False."""
    import modules.image_generator as ig
    import modules.swarm_director as sd

    def _boom(*a, **kw):
        raise AssertionError("image API called despite allow_ai_image=False!")

    monkeypatch.setattr(ig, "generate_image_bytes", _boom)
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    swarm = sd.SwarmDirector(eng)
    result = swarm.execute_swarm_campaign("Probe", "T", "a", "x", allow_ai_image=False)
    assert "hero_image.jpg" not in result["visual_files"]


def test_online_swarm_includes_image_when_api_works(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_online_key")
    monkeypatch.setenv("BRANDFORGE_PUBLIC_IMAGES", "1")
    import modules.image_generator as ig
    import modules.swarm_director as sd
    fake_jpg = b"\xff\xd8\xff\xe0FAKEJPG"
    monkeypatch.setattr(ig, "generate_image_bytes", lambda *a, **kw: fake_jpg)
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    eng.provider = "groq"  # simulate connected online provider
    swarm = sd.SwarmDirector(eng)
    result = swarm.execute_swarm_campaign("Probe", "T", "a", "x")
    assert result["visual_files"].get("hero_image.jpg") == fake_jpg
    assert result["meta"]["ai_image"] is True


def test_project_manager_saves_binary_files(tmp_path):
    from modules.project_manager import ProjectManager
    pm = ProjectManager(base_dir=str(tmp_path))
    jpg = b"\xff\xd8\xff\xe0binarydata"
    out = pm.save_campaign("bin_test",
                           {"product_name": "P", "strategy_text": "s"},
                           {"copy_text": "c"},
                           {"hero_banner.svg": "<svg></svg>", "hero_image.jpg": jpg})
    p = os.path.join(out, "hero_image.jpg")
    assert os.path.exists(p)
    with open(p, "rb") as f:
        assert f.read() == jpg


def test_image_module_returns_none_on_garbage():
    from modules.image_generator import generate_image_bytes
    assert generate_image_bytes("") is None
    assert generate_image_bytes("!!!@@@") is None


def test_image_endpoint_ssrf_blocklist(monkeypatch):
    """Operator override must never reach loopback/private/metadata hosts —
    the same SSRF policy web_searcher enforces (finding 3.3)."""
    import requests as _rq
    from modules.image_generator import generate_image_bytes

    called = []
    monkeypatch.setattr(_rq, "get", lambda *a, **kw: called.append(a) or None)

    for bad in (
        "http://127.0.0.1:8080/gen?p={prompt}",
        "http://localhost/gen?p={prompt}",
        "http://169.254.169.254/latest/meta-data/{prompt}",
        "http://[::1]/gen?p={prompt}",
        "http://[::ffff:127.0.0.1]/gen?p={prompt}",
        "http://10.0.0.8/gen?p={prompt}",
        "http://192.168.1.10/gen?p={prompt}",
        "http://metadata.google.internal/{prompt}",
        "file:///etc/passwd",
    ):
        monkeypatch.setenv("BRANDFORGE_IMAGE_ENDPOINT", bad)
        assert generate_image_bytes("probe") is None, bad
    assert not called
    monkeypatch.delenv("BRANDFORGE_IMAGE_ENDPOINT", raising=False)


def test_ics_tool_creates_valid_calendar(tmp_path, monkeypatch):
    monkeypatch.setenv("BRANDFORGE_DATA_DIR", str(tmp_path))
    from modules.mcp_registry import MCPRegistry
    reg = MCPRegistry(base_dir=str(tmp_path))
    r = reg.execute_tool("calendar_ics", {"product": "Apex Coffee", "industry": "Coffee"})
    assert "saved_to" in r and r["events"] == 30
    content = open(r["saved_to"], encoding="utf-8").read()
    assert content.startswith("BEGIN:VCALENDAR")
    assert content.count("BEGIN:VEVENT") == 30
    assert content.rstrip().endswith("END:VCALENDAR")


def test_generate_image_tool_honest_when_api_down(monkeypatch):
    import modules.image_generator as ig
    monkeypatch.setattr(ig, "generate_image_bytes", lambda *a, **kw: None)
    from modules.mcp_registry import MCPRegistry
    reg = MCPRegistry(base_dir="/tmp/vg_img_tool_test")
    r = reg.execute_tool("generate_image", {"prompt": "test product hero"})
    assert r.get("image") is None
    assert "unavailable" in r.get("note", "").lower()
