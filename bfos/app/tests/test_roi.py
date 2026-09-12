from modules.mcp_registry import MCPRegistry


def setup_function(f):
    f.registry = MCPRegistry()


def test_roi_standard():
    r = MCPRegistry()._tool_roi_calc(200)
    assert r["three_year_saas"] == 7200
    assert r["you_save"] == 7001  # $7,200 - $199 (Owner entry price)
    assert r["roi_percent"] == 3518.1
    assert r["payback_days"] == 29.9


def test_roi_custom_price():
    r = MCPRegistry()._tool_roi_calc(50, brandforge_price=99)
    assert r["you_save"] == 1701


def test_roi_zero_spend():
    r = MCPRegistry()._tool_roi_calc(0)
    assert r["payback_days"] == 0


def test_roi_invalid():
    assert "error" in MCPRegistry()._tool_roi_calc("abc")
    assert "error" in MCPRegistry()._tool_roi_calc(-5)
    assert "error" in MCPRegistry()._tool_roi_calc(1e9)
