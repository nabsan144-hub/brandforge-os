import os



def test_safe_slug_blocks_traversal():
    from server import _safe_slug
    assert _safe_slug("../../../etc/passwd") == "etc_passwd"
    assert _safe_slug("..") == "default"
    assert _safe_slug("a/b\\c") == "a_b_c"
    assert _safe_slug("") == "default"


def test_safe_slug_normalizes():
    from server import _safe_slug
    assert _safe_slug("Apex Coffee Launch!") == "apex_coffee_launch"
    assert _safe_slug("x" * 200, 60) == "x" * 60


def test_safe_text_strips_and_escapes():
    from server import _safe_text
    out = _safe_text("<script>alert(1)</script>hello")
    assert "<script>" not in out
    assert "<" not in out  # all tags stripped before escaping
    assert "alert(1)hello" in out
    assert _safe_text("") == ""


def test_safe_filename_preserves_extension_and_blocks_traversal():
    from modules.project_manager import _safe_filename
    assert _safe_filename("hero_banner.svg") == "hero_banner.svg"
    assert _safe_filename("../../etc/passwd") != "passwd"
    assert "/etc" not in _safe_filename("../../etc/passwd")
    assert "/" not in _safe_filename("a/b\\c.txt")  # no path separators survive
    assert _safe_filename("a/b\\c.txt").endswith(".txt")
    assert _safe_filename("evil.php") == "evil.php.txt"
    assert _safe_filename("") == "file.txt"


def test_safe_hex():
    from modules.visual_designer import _safe_hex
    assert _safe_hex("#E8B54A") == "#E8B54A"
    assert _safe_hex("f59e0b") == "#F59E0B"  # any valid hex normalizes, not just the brand gold
    assert _safe_hex("#F9B") == "#FF99BB"
    assert _safe_hex("not-a-color") == "#E8B54A"
    assert _safe_hex("#GGGGGG") == "#E8B54A"


def test_client_manager_color_validation():
    from modules.client_manager import ClientManager
    cm = ClientManager(base_dir="/tmp/vg_test_clients")
    cid = cm.save_client({"client_name": "Test Co", "primary_color": "javascript:alert(1)"})
    data = cm.get_client(cid)
    assert data["primary_color"] == "#E8B54A"  # invalid → fallback


def test_project_manager_traversal_containment(tmp_path):
    from modules.project_manager import ProjectManager
    pm = ProjectManager(base_dir=str(tmp_path))
    p = pm._campaign_path("../../../evil")
    assert os.path.commonpath([os.path.abspath(pm.campaigns_dir), os.path.abspath(p)]) == os.path.abspath(pm.campaigns_dir)

def test_api_key_rejects_newline_injection():
    """A 'key' containing newlines would corrupt the .env line structure."""
    from engines.ai_engine import AIEngine
    eng = AIEngine.__new__(AIEngine)  # don't touch disk
    eng.config = {}
    eng.env_file = "/tmp/vg_test_never_written.env"
    eng.api_key = None
    assert AIEngine.save_api_key(eng, "line1\nline2") is False
    assert AIEngine.save_api_key(eng, "ab\rcd") is False
    import os
    assert not os.path.exists(eng.env_file)


def test_landing_page_escapes_cta_text():
    """MEDIUM-01 regression: cta_text was the one unescaped string wired into
    generated landing pages (3 call sites) — a stored-XSS landmine for any
    future feature that feeds it from a form field or LLM output."""
    from modules.visual_designer import VisualDesigner
    designer = VisualDesigner()
    html_out = designer.generate_landing_page(
        "P", "I", "A", ["b"], cta_text='<script>alert(1)</script>')
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out  # rendered inert, still visible as text


def test_landing_page_escapes_all_influenced_fields():
    from modules.visual_designer import VisualDesigner
    designer = VisualDesigner()
    html_out = designer.generate_landing_page(
        '<img src=x onerror="alert(1)">', '<b>Ind', '<u>Aud',
        ['<li>bad</li>'], cta_text='" onmouseover="alert(1)')
    assert '<img src=x' not in html_out
    assert '<script>' not in html_out and '<b>Ind' not in html_out
    assert html_out.count("&lt;") >= 5  # everything escaped, nothing dropped


def test_atomic_write_survives_missing_fchmod_windows(monkeypatch, tmp_path):
    """Windows has no os.fchmod — mode'd atomic writes must still succeed
    (permissions best-effort, integrity mandatory)."""
    monkeypatch.delattr(os, "fchmod", raising=False)
    from modules.security import atomic_write_text
    target = tmp_path / "cfg.json"
    atomic_write_text(str(target), '{"ok": true}', mode=0o600)
    assert target.read_text() == '{"ok": true}'
