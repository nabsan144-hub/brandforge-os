from modules.mcp_registry import MCPRegistry

EXPECTED_21 = {
    "web_search", "inspect_url", "competitor_audit", "competitor_compare",
    "generate_copy", "email_sequence", "social_calendar", "keyword_brief",
    "brand_strategy", "seo_analyze", "generate_visual", "landing_page",
    "generate_image", "calendar_ics",
    "roi_calculator", "list_campaigns", "search_memory", "save_memory",
    # NEW: high-end design + custom sizes
    "generate_logo", "branding_kit", "generate_custom_visual",
}


def test_exactly_21_real_tools():
    reg = MCPRegistry()
    assert set(reg.tools.keys()) == EXPECTED_21
    assert len(reg.list_tools()) == 21


def test_unknown_tool():
    reg = MCPRegistry()
    r = reg.execute_tool("nonexistent_tool", {})
    assert "error" in r


def test_args_validation():
    reg = MCPRegistry()
    assert "error" in reg.execute_tool("web_search", "not-a-dict")
    assert "error" in reg.execute_tool("web_search", {"query": "x" * 300})
    assert "error" in reg.execute_tool("roi_calculator", {"monthly_spend": "abc"})


def test_email_sequence():
    reg = MCPRegistry()
    r = reg.execute_tool("email_sequence", {"product": "Apex", "benefits": "organic,fast", "audience": "pros"})
    assert len(r["sequence"]) == 5
    assert all(e["subject"] for e in r["sequence"])


def test_social_calendar_30_days():
    reg = MCPRegistry()
    r = reg.execute_tool("social_calendar", {"product": "Apex", "industry": "retail", "audience": "pros"})
    assert r["days"] == 30 and len(r["posts"]) == 30


def test_keyword_brief():
    reg = MCPRegistry()
    r = reg.execute_tool("keyword_brief", {"product": "Apex Coffee", "industry": "retail", "audience": "pros", "benefits": "organic, fast, local"})
    assert len(r["keywords"]) >= 4
    assert all(k["intent"] in ("brand", "commercial", "informational") for k in r["keywords"])


def test_landing_page():
    reg = MCPRegistry()
    r = reg.execute_tool("landing_page", {"product": "Apex", "industry": "retail", "audience": "pros", "benefits": "organic, fast"})
    assert "<!DOCTYPE html>" in r["preview"]


def test_seo_analyze():
    reg = MCPRegistry()
    r = reg.execute_tool("seo_analyze", {"text": ("coffee " * 400) + "# Head", "keyword": "coffee"})
    assert 0 <= r["score"] <= 100
    assert r["has_keyword"] is True


def test_generate_visual_escaped():
    reg = MCPRegistry()
    r = reg.execute_tool("generate_visual", {"product": "<script>alert(1)</script>", "headline": "x"})
    assert "<script>alert" not in r.get("svg_preview", "")


def test_search_memory_roundtrip(tmp_path):
    from modules.memory_manager import MemoryManager
    mm = MemoryManager(base_dir=str(tmp_path))
    mm.save_long_term("TestKey", "test value 123")
    assert "TestKey" in mm.get_long_term_memory()
    r = mm.search_history("test value", limit=3)
    assert isinstance(r, list)


def test_generate_logo():
    reg = MCPRegistry()
    r = reg.execute_tool("generate_logo", {"brand": "Apex Coffee", "style": "lettermark", "primary_color": "#E8B54A"})
    assert "svg_preview" in r
    assert "<svg" in r["svg_preview"]
    assert r["width"] == 1024


def test_branding_kit():
    reg = MCPRegistry()
    r = reg.execute_tool("branding_kit", {"brand": "Apex Coffee", "primary_color": "#E8B54A", "secondary_color": "#0F172A", "industry": "Retail"})
    assert r["count"] >= 9
    assert "primary_logo.svg" in r["files"] or any("primary_logo" in f for f in r["files"])
    assert "branding_" in r["kit_dir"]


def test_generate_custom_visual():
    reg = MCPRegistry()
    r = reg.execute_tool("generate_custom_visual", {"product": "Apex", "width": 300, "height": 250, "preset": "medium_rectangle"})
    assert r["width"] == 300 and r["height"] == 250
    assert "svg_preview" in r
    assert "Medium Rectangle" in r["description"] or "medium_rectangle" in r["preset"] or r["preset"] == "medium_rectangle"
    # custom size any
    r2 = reg.execute_tool("generate_custom_visual", {"product": "Apex", "width": 500, "height": 500})
    assert r2["width"] == 500 and r2["height"] == 500
