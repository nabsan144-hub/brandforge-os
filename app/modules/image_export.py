"""Raster export (PNG/JPEG) for the SVG deliverables — ad platforms need raster.

Why: Meta/Google/LinkedIn ad uploaders accept PNG/JPEG, not SVG. The SVG
remains the editable master; this module renders pixel-perfect copies with
resvg (the Rust resvg library — same fidelity browsers use for SVG), so what
you preview is what uploads.

Honesty rules (same as the rest of the app):
- resvg-py is a core pinned dependency; if it is somehow missing we degrade
  to SVG-only and say so — we never write a broken or blank raster file.
- Every render is checked (non-empty, PNG/JPEG magic bytes) before it is
  added to the campaign pack.
"""
from __future__ import annotations

import io
from typing import Dict, Optional

try:
    import resvg_py as _resvg
    PNG_EXPORT_AVAILABLE = True
except ImportError:  # pragma: no cover — optional at runtime, tested elsewhere
    _resvg = None
    PNG_EXPORT_AVAILABLE = False

try:
    from PIL import Image
    _PIL = True
except ImportError:  # pragma: no cover
    _PIL = False
    Image = None


def svg_to_png_bytes(svg_str: str, width: Optional[int] = None,
                     height: Optional[int] = None) -> bytes:
    """Render an SVG string to PNG bytes via resvg. Raises if unavailable."""
    if not PNG_EXPORT_AVAILABLE:
        raise RuntimeError("resvg-py is not installed — run: pip install resvg-py")
    try:
        png = _resvg.svg_to_bytes(svg_string=svg_str, width=width, height=height)
    except ValueError as e:
        # resvg rejects malformed SVG with ValueError — normalize to our contract.
        raise RuntimeError(f"resvg could not render this SVG: {e}") from e
    if not png or len(png) < 100 or not png.startswith(b"\x89PNG"):
        raise RuntimeError("resvg returned an empty/invalid PNG — refusing to ship it")
    return png


def png_bytes_to_jpeg_bytes(png_bytes: bytes, background: str = "#FFFFFF",
                            quality: int = 88) -> bytes:
    """Flatten PNG onto a solid background and re-encode as JPEG."""
    if not _PIL:
        raise RuntimeError("Pillow is not installed — JPEG export unavailable")
    im = Image.open(io.BytesIO(png_bytes))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, background)
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    out = io.BytesIO()
    im.save(out, "JPEG", quality=quality, optimize=True)
    data = out.getvalue()
    if not data.startswith(b"\xff\xd8"):
        raise RuntimeError("JPEG re-encode failed — refusing to ship it")
    return data


# Files that also get a JPEG twin (the two placements ad platforms want most).
_JPEG_TWIN_STEMS = ("hero_banner", "instagram_square")


def export_visual_rasters(visual_files: Dict[str, object]) -> Dict[str, bytes]:
    """Render every .svg deliverable to .png (natural size), plus .jpg twins
    for the main ad placements. Returns NEW files only — caller merges them.

    Sizes come from each SVG's own width/height (hero 1200x630, IG 1080x1080,
    favicon 512, avatar 500, custom banners at their requested size), so the
    raster always matches the vector exactly.
    """
    added: Dict[str, bytes] = {}
    svg_items = [(k, v) for k, v in visual_files.items()
                 if k.lower().endswith(".svg") and isinstance(v, str)]
    for name, svg in svg_items:
        try:
            png = svg_to_png_bytes(svg)
        except Exception:
            # One bad render must not sink the pack — skip that file, keep the SVG.
            continue
        png_name = name[:-4] + ".png"
        if png_name not in visual_files:
            added[png_name] = png
        stem = name.split("/")[-1][:-4]
        if stem in _JPEG_TWIN_STEMS:
            try:
                added[name[:-4] + ".jpg"] = png_bytes_to_jpeg_bytes(png)
            except Exception:
                continue
    return added
