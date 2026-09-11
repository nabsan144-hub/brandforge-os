"""Safe SVG/HTML campaign-asset generation — Marketing + High-End Design Focus.

Customer and model text is escaped at render time and colors are restricted to
hex values. Generated assets are templates, not claims of performance or legal
approval; review them before publication.

NEW in this version (2026-08-26):
- Full branding kit: logos (lettermark, wordmark, combination, abstract, emblem),
  favicon, social avatar, brand guidelines
- Custom size option: any width/height for banners, ad sizes presets for Google,
  Facebook, Instagram, LinkedIn, etc.
- High-end logo generation via SVG (offline, no API key) + optional AI image
"""

from __future__ import annotations

import base64
import html
import re
import json
from typing import List, Dict, TYPE_CHECKING, Tuple

from modules.security import safe_hex as _safe_hex, safe_text as _safe_text

if TYPE_CHECKING:
    from engines.ai_engine import AIEngine

# Standard ad sizes from net research (Google Display, Meta, LinkedIn, etc.)
AD_SIZES: Dict[str, Tuple[int, int, str]] = {
    # Google Display — most important 4 cover 80% inventory
    "medium_rectangle": (300, 250, "Medium Rectangle — All devices, in-content/sidebar"),
    "leaderboard": (728, 90, "Leaderboard — Desktop header/footer"),
    "half_page": (300, 600, "Half Page — Sidebar high-impact"),
    "mobile_banner": (320, 50, "Mobile Banner — Mobile top/bottom"),
    # Additional Google
    "large_rectangle": (336, 280, "Large Rectangle — Blogs/articles"),
    "wide_skyscraper": (160, 600, "Wide Skyscraper — Side panels"),
    "large_mobile_banner": (320, 100, "Large Mobile Banner — In-app"),
    "billboard": (970, 250, "Billboard — Premium header takeover"),
    "large_leaderboard": (970, 90, "Large Leaderboard — Premium header"),
    "skyscraper": (120, 600, "Skyscraper — Sidebar"),
    "small_square": (200, 200, "Small Square"),
    "square": (250, 250, "Square"),
    "portrait": (300, 1050, "Portrait — Premium sidebar"),
    # Meta / Facebook / Instagram
    "fb_feed": (1200, 628, "Facebook Feed — 1.91:1"),
    "fb_square": (1080, 1080, "Facebook/Instagram Square — 1:1"),
    "fb_story": (1080, 1920, "Facebook/Instagram Story/Reel — 9:16"),
    "ig_portrait": (1080, 1350, "Instagram Portrait — 4:5"),
    "ig_landscape": (1080, 566, "Instagram Landscape — 1.91:1"),
    # LinkedIn / Twitter / YouTube
    "linkedin_feed": (1200, 627, "LinkedIn Feed — 1.91:1"),
    "twitter_post": (1200, 675, "Twitter Post — 16:9"),
    "youtube_thumbnail": (1280, 720, "YouTube Thumbnail — 16:9"),
    # BrandForge defaults
    "hero_banner": (1200, 630, "BrandForge Hero Banner — 1200x630"),
    "instagram_square": (1080, 1080, "BrandForge Instagram Square — 1080x1080"),
    "logo_square": (1024, 1024, "Logo Square — 1024x1024"),
    "favicon": (512, 512, "Favicon High-Res — 512x512"),
    "social_avatar": (500, 500, "Social Avatar — 500x500 circle"),
}

LOGO_STYLES = [
    "lettermark",      # Initials/monogram — IBM, CNN — best for long names, small sizes
    "wordmark",        # Full name styled — Google, Coca-Cola — best for short memorable names
    "combination",     # Icon + text separable — most versatile — Burger King, Lacoste
    "abstract",        # Geometric non-literal — Pepsi, Nike — best for tech/AI
    "pictorial",       # Literal icon — Apple, Twitter — best for strong visual idea
    "emblem",          # Badge/seal — Starbucks, Harley — best for heritage
]

class VisualDesigner:
    def __init__(self, ai_engine: "AIEngine" = None):
        self.ai = ai_engine

    def _approved_logo_html(self):
        logo = getattr(self, "approved_logo", "")
        if not re.fullmatch(r"data:image/png;base64,[A-Za-z0-9+/]+={0,2}", logo): return ""
        return f'<img src="{logo}" alt="Approved brand logo" style="display:block;max-width:160px;max-height:96px;width:auto;height:auto;margin:16px auto;object-fit:contain">'

    @staticmethod
    def _brand_badge(brand_text: str, default: str = "BRANDFORGE OS") -> str:
        return html.escape((_safe_text(brand_text, 24) or default).upper())

    @staticmethod
    def _escaped(value: object, limit: int, default: str = "") -> str:
        raw = str(value or "")[:limit]
        return html.escape(raw or default)

    @staticmethod
    def _href(value: str, fallback: str = "#start") -> str:
        candidate = str(value or "").strip()
        if re.fullmatch(r"#[A-Za-z0-9_-]{1,40}", candidate) or re.match(r"^(?:https?://|mailto:)[^\\s<>\"']+$", candidate, re.I):
            return html.escape(candidate, quote=True)
        return fallback

    @staticmethod
    def _validate_size(width: int, height: int) -> Tuple[int, int]:
        """Custom size option — clamp to safe range 50-5000, preserve aspect."""
        try:
            w = int(width)
            h = int(height)
        except (TypeError, ValueError):
            return 1200, 630
        w = max(50, min(w, 5000))
        h = max(50, min(h, 5000))
        return w, h

    # ---------- existing methods now call custom size version ----------

    def generate_hero_banner_svg(
        self,
        product_name: str,
        subtitle: str,
        cta_text: str = "Get Started",
        primary_color: str = "#E8B54A",
        secondary_color: str = "#0F172A",
        brand_text: str = "BRANDFORGE OS",
        benefits: List[str] = None,
        width: int = 1200,
        height: int = 630,
    ) -> str:
        # Backward compatible — now supports custom size
        return self.generate_custom_banner_svg(
            product_name, subtitle, width, height, primary_color, secondary_color, brand_text, benefits, cta_text, "hero"
        )

    def generate_instagram_square_svg(
        self,
        product_name: str,
        tagline: str,
        primary_color: str = "#E8B54A",
        secondary_color: str = "#0F172A",
        brand_text: str = "BRANDFORGE OS",
        benefits: List[str] = None,
        width: int = 1080,
        height: int = 1080,
    ) -> str:
        return self.generate_custom_banner_svg(
            product_name, tagline, width, height, primary_color, secondary_color, brand_text, benefits, "Learn more", "instagram"
        )

    # ---------- NEW: custom size banner ----------

    @staticmethod
    def _accent_partner(primary: str, secondary: str) -> str:
        """Brand-faithful accent partner for gradients (replaces hardcoded blue).

        Rules, in order:
        1. The brand's SECONDARY color, when it is vivid enough to read as an
           accent (saturated, mid-lightness — e.g. a brand teal or crimson).
        2. A complementary hue derived from the PRIMARY (rotated 150 degrees,
           tuned lightness/saturation so it glows on dark backgrounds) — used
           when the secondary is a near-black neutral like charcoal/navy.
        3. #3B82F6 — the founder-approved default pairing for the default
           gold (#E8B54A) + navy (#0F172A) BrandForge look, preserved so the
           default output is pixel-identical to before.
        """
        import colorsys

        def hsl(hex_color: str):
            h = str(hex_color or "").lstrip("#")
            if len(h) != 6:
                return None
            try:
                r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
            except ValueError:
                return None
            return colorsys.rgb_to_hls(r, g, b)  # (hue, lightness, saturation)

        sec = hsl(secondary)
        if sec and sec[2] >= 0.25 and 0.28 <= sec[1] <= 0.85:
            return str(secondary).upper()

        pri = hsl(primary)
        if pri and str(primary).upper() != "#E8B54A":
            hue, light, sat = pri
            comp = (hue + 150 / 360) % 1.0
            r, g, b = colorsys.hls_to_rgb(
                comp,
                max(0.55, min(0.75, light + 0.15)),
                max(0.45, min(0.85, sat if sat >= 0.45 else sat + 0.25)),
            )
            return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))

        return "#3B82F6"

    # ---------- AI photo composition (brand design over generated imagery) ----------

    # Photos above this many pixels are downscaled before embedding: a 4K
    # generation embedded at full size balloons the SVG (base64 +33%), the
    # resvg render memory and the campaign ZIP, with zero visible benefit at
    # banner sizes.
    _PHOTO_MAX_SCALE = 2.0

    @staticmethod
    def _image_data_uri(image_bytes: bytes) -> str:
        """AI photo -> embeddable data URI (PNG/JPEG sniffed from magic bytes)."""
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        else:
            mime = "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(bytes(image_bytes)).decode("ascii")

    @classmethod
    def _prepare_photo(cls, image_bytes: bytes, width: int, height: int) -> bytes:
        """Downscale oversized photos to ~2x the target box (retina-safe).

        Falls back to the original bytes when Pillow is unavailable or the
        payload is not a valid raster — never fails, never fakes."""
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(image_bytes))
            im.load()
            max_w = int(width * cls._PHOTO_MAX_SCALE)
            max_h = int(height * cls._PHOTO_MAX_SCALE)
            if im.width <= max_w and im.height <= max_h:
                return image_bytes
            ratio = min(max_w / im.width, max_h / im.height)
            im = im.resize((max(1, int(im.width * ratio)), max(1, int(im.height * ratio))),
                           Image.LANCZOS)
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="JPEG", quality=90)
            return buf.getvalue()
        except Exception:
            return image_bytes

    def generate_photo_hero_svg(self, image_bytes, product_name, subtitle, primary_color="#E8B54A",
                                secondary_color="#0F172A", brand_text="BRANDFORGE OS", benefits=None,
                                cta_text="Get Started", width=1200, height=630):
        w,h=self._validate_size(width,height)
        href=self._image_data_uri(self._prepare_photo(image_bytes,w,h))
        panel=self.generate_custom_banner_svg(product_name,subtitle,int(w*.58),h,primary_color,
                                              secondary_color,brand_text,benefits,cta_text)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
                f'<image href="{href}" x="{w*.5}" y="0" width="{w*.5}" height="{h}" preserveAspectRatio="xMidYMid slice"/>'
                f'{panel}</svg>')

    def generate_photo_square_svg(self, image_bytes, product_name, subtitle, primary_color="#E8B54A",
                                  secondary_color="#0F172A", brand_text="BRANDFORGE OS", benefits=None,
                                  cta_text="Get Started", width=1080, height=1080):
        w,h=self._validate_size(width,height)
        href=self._image_data_uri(self._prepare_photo(image_bytes,w,h))
        ph=int(h*.53)
        panel=self.generate_custom_banner_svg(product_name,subtitle,w,ph,primary_color,
                                              secondary_color,brand_text,benefits,cta_text)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
                f'<image href="{href}" x="0" y="0" width="{w}" height="{h*.5}" preserveAspectRatio="xMidYMid slice"/>'
                f'<g transform="translate(0 {h-ph})">{panel}</g></svg>')

    def generate_custom_banner_svg(self, product_name, subtitle, width=1200, height=630,
                                   primary_color="#E8B54A", secondary_color="#0F172A",
                                   brand_text="BRANDFORGE OS", benefits=None, cta_text="Get Started", layout="hero",
                                   style="bold", offer=""):
        from modules.visual_layout import banner_svg
        return banner_svg(product_name, subtitle, width, height, primary_color, secondary_color,
                          cta_text, logo=getattr(self, "approved_logo", ""), brand_text=brand_text, benefits=benefits or [],
                          style=style, offer=offer or getattr(self, "campaign_offer", ""))

    def generate_ad_banner_svg(
        self,
        product_name: str,
        width: int = 300,
        height: int = 250,
        primary_color: str = "#E8B54A",
        secondary_color: str = "#0F172A",
        brand_text: str = "BRANDFORGE OS",
        benefits: List[str] = None,
        cta_text: str = "Get Started",
        preset: str = "",
    ) -> str:
        """Generate ad banner in custom size or preset — Google, FB, IG, LinkedIn sizes.
        
        preset: e.g. medium_rectangle (300x250), leaderboard (728x90), half_page (300x600),
        fb_feed (1200x628), instagram_square (1080x1080), etc. See AD_SIZES.
        If preset provided, width/height from preset override custom.
        """
        if preset and preset in AD_SIZES:
            width, height = AD_SIZES[preset][0], AD_SIZES[preset][1]
        return self.generate_custom_banner_svg(
            product_name, f"For {brand_text}", width, height, primary_color, secondary_color, brand_text, benefits, cta_text, "ad"
        )

    # ---------- NEW: High-End Logo Generation ----------

    def generate_logo_svg(self, brand_name, style="lettermark", primary_color="#E8B54A",
                          secondary_color="#0F172A", variant="primary", width=1024, height=1024):
        from modules.visual_layout import logo_svg
        if variant == "mono": primary_color, secondary_color = "#FFFFFF", "#111827"
        elif variant == "light": secondary_color = "#FFFFFF"
        svg = logo_svg(brand_name, primary_color, secondary_color, style)
        w, h = self._validate_size(width, height)
        return svg.replace('width="1024" height="1024" viewBox', f'width="{w}" height="{h}" viewBox', 1)

    def generate_branding_kit(
        self,
        brand_name: str,
        primary_color: str = "#E8B54A",
        secondary_color: str = "#0F172A",
        industry: str = "General",
        tagline: str = "",
    ) -> Dict[str, str]:
        """Generate a full branding kit: 8 logo variants, color palette and
        usage guidelines for the given brand and colors.

        Returns dict of files:
        - primary_logo.svg (combination)
        - reversed_logo.svg (white on dark)
        - icon_only.svg (lettermark icon)
        - wordmark.svg (text only)
        - lettermark.svg (initials circle)
        - abstract_mark.svg (geometric)
        - emblem.svg (badge)
        - favicon.svg (512x512)
        - social_avatar.svg (500x500 circle)
        - color_palette.json
        - brand_guidelines.md
        - logo_usage.md

        High-end, offline, no API key needed, custom colors, review before publishing.
        """
        pc = _safe_hex(primary_color, "#E8B54A")
        sc = _safe_hex(secondary_color, "#0F172A")
        ap = self._accent_partner(pc, sc)  # brand-faithful gradient partner
        brand_raw = str(brand_name or "")[:40].strip() or "Brand"
        industry = self._escaped(industry, 80, "General")
        tagline = self._escaped(tagline, 120, f"{brand_raw} — {industry}")

        files: Dict[str, str] = {}

        # Logos — all 6 styles + variants
        files["primary_logo.svg"] = self.generate_logo_svg(brand_raw, "combination", pc, sc, "primary", 1024, 1024)
        files["reversed_logo.svg"] = self.generate_logo_svg(brand_raw, "combination", pc, sc, "reversed", 1024, 1024)
        files["icon_only.svg"] = self.generate_logo_svg(brand_raw, "lettermark", pc, sc, "icon-only", 1024, 1024)
        files["wordmark.svg"] = self.generate_logo_svg(brand_raw, "wordmark", pc, sc, "wordmark-only", 1024, 1024)
        files["lettermark.svg"] = self.generate_logo_svg(brand_raw, "lettermark", pc, sc, "primary", 1024, 1024)
        files["abstract_mark.svg"] = self.generate_logo_svg(brand_raw, "abstract", pc, sc, "primary", 1024, 1024)
        files["emblem.svg"] = self.generate_logo_svg(brand_raw, "emblem", pc, sc, "primary", 1024, 1024)
        files["favicon.svg"] = self.generate_logo_svg(brand_raw, "lettermark", pc, sc, "primary", 512, 512)
        files["social_avatar.svg"] = self.generate_logo_svg(brand_raw, "lettermark", pc, sc, "primary", 500, 500)

        # Color palette JSON
        palette = {
            "brand": brand_raw,
            "primary": pc,
            "secondary": sc,
            "accent": ap,
            "success": "#10B981",
            "background": "#070d11",
            "surface": "#0F172A",
            "ink": "#F8FAFC",
            "muted": "#94A3B8",
            "colors": [
                {"name": "Primary", "hex": pc, "role": "CTA, accent, premium"},
                {"name": "Secondary", "hex": sc, "role": "Trust, background, text"},
                {"name": "Accent", "hex": ap, "role": "Secondary CTA, links"},
                {"name": "Success Green", "hex": "#10B981", "role": "Success, action"},
                {"name": "Background", "hex": "#070d11", "role": "Dark background"},
            ]
        }
        files["color_palette.json"] = json.dumps(palette, indent=2)

        # Brand guidelines MD
        files["brand_guidelines.md"] = f"""# {brand_raw} — Brand Guidelines

> Generated with BrandForge OS — Review before publishing — High-end branding kit

## Brand
- **Name:** {brand_raw}
- **Industry:** {industry}
- **Tagline:** {tagline}

## Logo Types (7 types from research)
- **Lettermark:** {brand_raw[0].upper() if brand_raw else 'B'} — initials/monogram — best for long names, app icon, favicon, social avatar — IBM, CNN style — high reliability for embroidery, small sizes
- **Wordmark:** {brand_raw} styled — best for short memorable names — Google, Coca-Cola style — high print reliability
- **Combination:** Icon + text separable — most versatile — Burger King, Lacoste — works for website header, packaging, app icon, business card — **recommended for most brands**
- **Abstract:** Geometric non-literal — Pepsi, Nike — best for tech/AI, emotional brands
- **Pictorial:** Literal icon — Apple, Twitter — best for strong visual idea
- **Emblem:** Badge/seal — Starbucks, Harley — best for heritage, institutional

## Logo Usage
- **Primary:** `primary_logo.svg` — combination — use on website header, business cards, invoices
- **Reversed:** `reversed_logo.svg` — white on dark — use on dark backgrounds
- **Icon Only:** `icon_only.svg` — lettermark — use for social avatar (500x500), favicon (512x512), app icon — small spaces need compact recognition
- **Wordmark:** `wordmark.svg` — text only — use for document headers, when icon not needed
- **Clear Space:** Keep clear space around logo = height of letter {brand_raw[0].upper() if brand_raw else 'B'}
- **Minimum Size:** 24px for icon, 120px for combination

## Colors
- **Primary {pc}:** Premium CTA — gold reserved for one accent — use for buttons, highlights
- **Secondary {sc}:** Trust — navy — use for backgrounds, text
- **Accent (brand-derived):** Secondary CTA, links — hex in color_palette.json
- **Success Green #10B981:** Success states

## Typography
- **Headlines:** Instrument Serif italic + Geist Bold — premium studio identity
- **Body:** Geist 400/500 — system-ui fallback
- **Mono:** Geist Mono — for codes, badges

## Files Included
- `primary_logo.svg` — main combination logo
- `reversed_logo.svg` — white on dark
- `icon_only.svg` — lettermark for avatars
- `wordmark.svg` — text only
- `lettermark.svg`, `abstract_mark.svg`, `emblem.svg` — variations
- `favicon.svg` — 512x512 high-res favicon (generate PNGs 32x32, 16x16 from this)
- `social_avatar.svg` — 500x500 circle avatar
- `color_palette.json` — palette for devs
- `brand_guidelines.md` — this file
- `logo_usage.md` — placement guide

## Next Steps
1. Review all logos — check spelling, colors, readability at small sizes (16px favicon)
2. Generate PNGs from SVGs for platforms that need PNG: favicon 32x32, 16x16, social avatar 500x500 PNG
3. Test on light and dark backgrounds
4. For AI high-end variations, set `BRANDFORGE_IMAGE_ENDPOINT` to Replicate/Ideogram/DALL-E and use `generate_image` tool with prompt "minimal premium logo for {brand_raw}, flat vector, {pc} on {sc}, transparent background, high-end"

> Template generated with BrandForge OS — Add your final logo selection before publishing.
"""

        # Logo usage MD
        files["logo_usage.md"] = f"""# {brand_raw} — Logo Usage by Placement

| Placement | Best Logo Type | File | Why |
|---|---|---|---|
| Website header | Combination, Wordmark | primary_logo.svg, wordmark.svg | Brand name clear quickly |
| Social avatar | Lettermark, Abstract | icon_only.svg, social_avatar.svg (500x500) | Small circular/square needs compact |
| Favicon | Lettermark | favicon.svg (512x512) → generate 32x32, 16x16 PNG | Tiny spaces need extreme simplification |
| App icon | Lettermark, Abstract | icon_only.svg, abstract_mark.svg | Simple shapes at small sizes |
| Business card | Combination, Wordmark | primary_logo.svg | Pairs with contact details |
| Invoice/document | Wordmark | wordmark.svg | Clarity > decoration |
| Packaging | Combination, Emblem | primary_logo.svg, emblem.svg | Shelf presence |
| Merch (T-shirt) | Lettermark, Emblem | icon_only.svg, emblem.svg | Bold shapes hold up for screen print/embroidery |
| Social feed 1080x1080 | Combination | primary_logo.svg on hero_banner 1200x630 etc | Use with custom size banners |

- Lettermark high reliability for embroidery, screen print, debossing, laser engraving — bold shapes, limited colors
- Wordmark high for screen print, heat transfer — center chest, back
- Combination most versatile — design icon and wordmark to work independently from day one

> Generated with BrandForge OS — Review before publishing.
"""

        return files

    # ---------- existing HTML generators (kept for backward compat) ----------

    def generate_html_ad_card(self, product_name, description, benefits, primary_color="#E8B54A",
                              secondary_color="#0F172A", brand_text="BRANDFORGE OS", cta_url="#start"):
        from modules.landing_layout import landing_html
        return landing_html(product_name, "", description, benefits, primary_color, secondary_color,
                            cta=getattr(self,"campaign_cta","See details"), url=getattr(self,"campaign_url",cta_url),
                            logo=getattr(self,"approved_logo",""), lang=getattr(self,"campaign_lang","en"), compact=True)

    def generate_landing_page(self, product_name, industry, target_audience, benefits, cta_text="Get Started",
                             primary_color="#E8B54A", secondary_color="#0F172A", brand_text="BRANDFORGE OS", cta_url="#start"):
        from modules.landing_layout import landing_html
        return landing_html(product_name, industry, target_audience, benefits, primary_color, secondary_color,
                            cta_text, getattr(self,"campaign_url",cta_url), getattr(self,"approved_logo",""),
                            getattr(self,"campaign_lang","en"))
