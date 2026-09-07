"""PNG/JPEG raster export of SVG deliverables (resvg-based).

Covers: PNG render + magic-byte checks, JPEG twin conversion, and the
campaign-level export hook (every SVG gets a PNG; hero + Instagram also get
a JPEG). Skips gracefully when resvg is not installed.
"""
import pytest

from modules.image_export import (
    PNG_EXPORT_AVAILABLE,
    export_visual_rasters,
    png_bytes_to_jpeg_bytes,
    svg_to_png_bytes,
)

MINI_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60" viewBox="0 0 120 60">'
    '<rect width="120" height="60" fill="#0F172A"/>'
    '<text x="10" y="35" fill="#E8B54A" font-family="sans-serif" font-size="16">Test</text>'
    "</svg>"
)

pytestmark = pytest.mark.skipif(
    not PNG_EXPORT_AVAILABLE, reason="resvg-py not installed (optional raster export)")


def test_svg_to_png_bytes_returns_valid_png():
    png = svg_to_png_bytes(MINI_SVG)
    assert png.startswith(b"\x89PNG") and len(png) > 200


def test_png_to_jpeg_flattens_transparency():
    png = svg_to_png_bytes(MINI_SVG)
    jpg = png_bytes_to_jpeg_bytes(png, background="#FFFFFF", quality=85)
    assert jpg.startswith(b"\xff\xd8")  # JPEG magic bytes


def test_bad_render_is_refused():
    with pytest.raises(RuntimeError):
        svg_to_png_bytes("this is not an svg at all")


def test_export_visual_rasters_adds_png_and_jpeg_twins():
    files = {
        "hero_banner.svg": MINI_SVG,
        "instagram_square.svg": MINI_SVG,
        "primary_logo.svg": MINI_SVG,
        "landing_page.html": "<html></html>",  # must be ignored
    }
    added = export_visual_rasters(files)
    assert "hero_banner.png" in added
    assert "hero_banner.jpg" in added
    assert "instagram_square.png" in added
    assert "instagram_square.jpg" in added
    assert "primary_logo.png" in added
    assert "primary_logo.jpg" not in added  # JPEG only for the two ad placements
    assert all(v.startswith(b"\x89PNG") for k, v in added.items() if k.endswith(".png"))
    assert all(v.startswith(b"\xff\xd8") for k, v in added.items() if k.endswith(".jpg"))


def test_export_never_overwrites_existing_files():
    files = {"hero_banner.svg": MINI_SVG, "hero_banner.png": b"\x89PNG-existing"}
    added = export_visual_rasters(files)
    assert "hero_banner.png" not in added  # existing file wins


def test_full_campaign_includes_rasters():
    """The swarm pipeline must ship PNG (+ hero JPEG) next to every SVG."""
    from engines.ai_engine import get_engine
    from modules.swarm_director import SwarmDirector

    eng = get_engine(provider="offline")
    director = SwarmDirector(eng)
    result = director.execute_swarm_campaign(
        product_name="Raster Test Co",
        industry="General",
        target_audience="Founders",
        key_benefits="Fast output, honest pricing",
        lang="en",
    )
    visuals = result["visual_files"]
    svg_names = [k for k in visuals if k.endswith(".svg")]
    assert svg_names, "campaign should generate SVGs"
    for name in svg_names:
        assert name[:-4] + ".png" in visuals, f"missing PNG twin for {name}"
    assert "hero_banner.jpg" in visuals and "instagram_square.jpg" in visuals
    assert result.get("png_export_status") == "ok"
