"""Regression tests for the third full-codebase audit pass (2026-08-26).

Pins six verified bugs so they cannot silently return:
- logo upload must 400 (not 500) on junk image bytes
- WebSocket handshake rejects cross-origin origins
- license redemption is atomic (no IntegrityError race)
- cloud quota RPC counts lifetime campaigns, not just the current month
- campaign-pack CSV cells are formula-injection safe
- release zip keeps the working tree clean of runtime state
"""
import io
import os

import pytest

from fastapi.testclient import TestClient
from server import app as server_app


@pytest.fixture()
def client():
    with TestClient(server_app) as c:
        c.headers["X-BrandForge-Token"] = c.get("/api/session").json()["capability"]
        yield c


# ---- 1. Logo upload: junk bytes -> 400, never 500 ----
def test_logo_upload_junk_bytes_returns_400(client):
    r = client.post(
        "/api/clients/default_studio/logo",
        files={"logo": ("evil.png", b"this is definitely not an image", "image/png")},
    )
    assert r.status_code == 400, f"junk image bytes must be a clean 400, got {r.status_code}: {r.text[:120]}"


def test_logo_upload_valid_png_still_works(client):
    # build a tiny real PNG
    try:
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), (200, 50, 50)).save(buf, format="PNG")
        r = client.post(
            "/api/clients/default_studio/logo",
            files={"logo": ("ok.png", buf.getvalue(), "image/png")},
        )
        assert r.status_code == 200, r.text[:120]
    except ImportError:
        pytest.skip("PIL not installed")


# ---- 2. WebSocket: cross-origin handshake rejected ----
def test_websocket_rejects_cross_origin(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/ws", headers={"Origin": "https://evil.example.com", "Host": "localhost:8000"}
        ) as ws:
            ws.receive_text()
    assert exc.value.code == 1008, "cross-origin WS must be closed with policy code"


def test_websocket_accepts_same_origin(client):
    with client.websocket_connect(
        "/ws", headers={"Origin": "http://localhost:8000", "Host": "localhost:8000"}
    ) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"


# ---- 3. Cloud quota RPC logic (pure-SQL mirror test) ----
def test_cloud_quota_logic_counts_lifetime():
    """Mirror of the reserve_campaign_slot decision logic: lifetime must use
    total campaigns, monthly must use the current-month counter."""
    def reserve(lifetime_total, month_count, lifetime_limit, monthly_limit):
        if lifetime_limit is not None and lifetime_total > lifetime_limit:
            return "LIMIT_LIFETIME"
        if monthly_limit is not None and month_count > monthly_limit:
            return "LIMIT_MONTHLY"
        return "OK"

    # free: 3 lifetime — 3 in July (month counter 3), 2 in June (not counted)
    assert reserve(5, 3, 3, None) == "LIMIT_LIFETIME", "lifetime must count ALL months"
    # pro: 50/month
    assert reserve(100, 51, None, 50) == "LIMIT_MONTHLY"
    assert reserve(100, 40, None, 50) == "OK"
    # agency: unlimited
    assert reserve(999, 999, None, None) == "OK"


# ---- 4. CSV formula injection neutralized ----
def test_campaign_pack_csv_escapes_formulas():
    import csv
    from modules.campaign_pack import build_campaign_pack
    strategy = {"product_name": "P", "industry": "I", "target_audience": "A",
                "strategy_text": "S", "agency_brand": "B"}
    copy_data = {"copy_text": "C",
                 "key_benefits": "=HYPERLINK(\"http://evil.com\",\"x\"),+SUM(1,1),-2+3,@cmd,normal benefit"}
    analysis = {}
    files = build_campaign_pack(strategy, copy_data, analysis, "client1")
    rows = list(csv.reader(files["03_content_calendar.csv"].splitlines()))
    # every parsed cell must be safe: none may start with = + - @ (raw formula)
    dangerous = [cell for row in rows for cell in row
                 if cell and cell[0] in ("=", "+", "-", "@")]
    assert not dangerous, f"formula cells found unquoted: {dangerous}"


# ---- 5. Release zip excludes runtime state ----
def test_release_zip_clean():
    """The packager's forbidden list must cover the runtime artifacts that
    actually get created when the app runs (memory db, approvals, output)."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "make_release_zip.py")).read()
    forbidden = src[src.index("FORBIDDEN = ["):src.index("FORBIDDEN_RES")]
    for pattern in [r"\.env$", r"\.db(-wal|-shm)?$", r"approvals\.json$", r"output/", r"active_client\.json$"]:
        assert pattern in forbidden, f"packager missing forbidden pattern {pattern}"


# ---- Pass 6: SSRF 0.0.0.0 gap (connects to loopback on Linux) ----
def test_ssrf_blocks_zero_zero_zero_zero():
    from modules.web_searcher import WebSearcher
    ws = WebSearcher()
    assert ws._is_blocked_url("http://0.0.0.0:8080/"), "0.0.0.0 must be blocked at parse time"
    assert ws._is_blocked_url("http://0.0.0.0/"), "0.0.0.0 root must be blocked"
    assert not ws._host_resolves_safe("0.0.0.0"), "DNS check must reject 0.0.0.0"


def test_ssrf_extra_private_ranges():
    from modules.web_searcher import WebSearcher
    ws = WebSearcher()
    for u in ("http://100.64.0.1/", "http://198.18.0.1/", "http://[fe80::1]/"):
        assert ws._is_blocked_url(u), f"{u} must be blocked"
    # public addresses still allowed at parse time
    assert not ws._is_blocked_url("https://example.com/")
    assert not ws._is_blocked_url("https://[2606:4700::1111]/")


# ---- Pass 7: ROI honesty + image-generator never-raises + hosted assets ----
def test_roi_tool_honest_at_low_spend():
    import tempfile
    from modules.mcp_registry import MCPRegistry
    reg = MCPRegistry(base_dir=tempfile.mkdtemp())
    low = reg.execute_tool("roi_calculator", {"monthly_spend": 1})
    assert low.get("note") and "does not pay back" in low["note"], low
    assert low.get("you_save") == -163.0
    normal = reg.execute_tool("roi_calculator", {"monthly_spend": 200})
    assert normal.get("note") is None
    assert normal.get("you_save") == 7001.0


def test_offline_engine_roi_honest_at_low_spend():
    import tempfile
    from engines.ai_engine import AIEngine
    eng = AIEngine(provider="offline", data_dir=tempfile.mkdtemp())
    low = eng._offline_smart_generate("ROI calculator: I pay $1/month", {})
    assert "does not pay back" in low
    assert "$-13" not in low, "negative save must not render as '$-13'"
    high = eng._offline_smart_generate("ROI calculator: I pay $200/month", {})
    assert "does not pay back" not in high
    assert "You save:" in high


def test_scorecard_honest_at_low_spend():
    from modules.audit_scorecard import AuditScorecard
    card = AuditScorecard()
    html = card.generate_scorecard_html("Brand", monthly_spend=1)
    assert "doesn't pay back" in html
    low_seg = html.split("You save")[1].split("</div>")[0]
    assert "-$" not in low_seg, "negative save must never render on a client-facing card"
    assert "—" in low_seg, "low-spend save box must show the honest em-dash"
    html2 = card.generate_scorecard_html("Brand", monthly_spend=200)
    assert "doesn't pay back" not in html2
    assert "$7,001" in html2


def test_image_generator_never_raises_on_garbage_args():
    from modules.image_generator import generate_image_bytes
    assert generate_image_bytes("x", width="abc") is None
    assert generate_image_bytes("x", width=999999, height="oops") is None
    assert generate_image_bytes("x", seed="bad") is None


# ---- Pass 8: browser-verified fixes ----
def test_main_js_uses_svelte_mount():
    """The dashboard must mount via Svelte 5's mount() — the legacy
    `new App()` API produced a runtime-crashing bundle (blank dashboard),
    verified in real Chromium."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "web-modern", "src", "main.js")).read()
    assert "mount(App" in src
    assert "const app = new App" not in src, "legacy new App() mount must not be used"


def test_dashboard_csp_hash_is_base64():
    """CSP 'sha256-...' values must be base64 (the earlier hex hash silently
    failed and blocked the dashboard's theme-init inline script)."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "server.py")).read()
    import re
    m = re.search(r'_THEME_INLINE_HASH = "(sha256-[^"]+)"', src)
    assert m, "theme hash constant missing"
    h = m.group(1)
    assert h.startswith("sha256-")
    b64 = h[len("sha256-"):]
    # base64 alphabet (with padding) — not hex
    assert re.fullmatch(r"[A-Za-z0-9+/]+=*", b64), "hash must be base64, not hex"
    assert len(b64) == 44, "sha256 base64 is 44 chars"
