from modules.visual_designer import VisualDesigner


def test_brand_faithful_accent_no_default_blue():
    """Custom brand colors must not leak the hardcoded #3B82F6 accent."""
    v = VisualDesigner()
    # terracotta + charcoal brand: secondary too dark to be an accent ->
    # complementary of terracotta is used, never the default blue.
    svg = v.generate_custom_banner_svg("Sindh Ceramics", "Tiles",
                                       primary_color="#C2410C",
                                       secondary_color="#1C1917")
    assert "#3B82F6" not in svg
    assert "#C2410C" in svg

    # vivid secondary (teal) becomes the accent partner itself
    svg2 = v.generate_custom_banner_svg("Co", "X",
                                        primary_color="#F59E0B",
                                        secondary_color="#0D9488")
    assert "#0D9488" in svg2
    assert "#3B82F6" not in svg2

    # default BrandForge look is preserved (gold + classic blue partner)
    svg3 = v.generate_custom_banner_svg("Default", "Look")
    assert "#3B82F6" in svg3

    # logo + palette follow the brand too
    logo = v.generate_logo_svg("Sindh Ceramics", "lettermark",
                               "#C2410C", "#1C1917", "primary", 400, 400)
    assert "#3B82F6" not in logo
    kit = v.generate_branding_kit("Sindh Ceramics",
                                  primary_color="#C2410C",
                                  secondary_color="#1C1917")
    import json
    palette = json.loads(kit["color_palette.json"])
    assert palette["accent"] != "#3B82F6"
