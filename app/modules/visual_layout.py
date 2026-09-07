"""Measured, script-shaped vector assets; no system-font dependency at export.

Noto fonts are bundled under the SIL Open Font License. Text remains editable
in the accompanying copy files; SVG text is outlined for portable rendering.
"""
from __future__ import annotations
import base64
import html
import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from modules.security import safe_hex

FONT_DIR = Path(__file__).resolve().parents[1] / "brandforge_assets" / "fonts"
FONT_NAMES = ("NotoSans", "NotoNaskhArabic", "NotoSansDevanagari")


@lru_cache(maxsize=1)
def _fonts():
    import uharfbuzz as hb
    from fontTools.ttLib import TTFont
    result = []
    for name in FONT_NAMES:
        path = FONT_DIR / f"{name}-Regular.ttf"
        font = TTFont(path)
        face = hb.Face(path.read_bytes())
        hfont = hb.Font(face)
        result.append((font, hfont, face.upem, font.getBestCmap(), font.getGlyphSet()))
    return result


@lru_cache(maxsize=2048)
def _path(face, name):
    from fontTools.pens.svgPathPen import SVGPathPen
    font, _, _, _, glyphs = _fonts()[face]
    pen = SVGPathPen(glyphs)
    glyphs[name].draw(pen)
    from fontTools.pens.boundsPen import BoundsPen
    bounds = BoundsPen(glyphs)
    glyphs[name].draw(bounds)
    return pen.getCommands(), bounds.bounds or (0, 0, 0, 0)


@lru_cache(maxsize=512)
def _shape(text):
    import uharfbuzz as hb
    fs = _fonts()
    groups = []
    for ch in str(text):
        face = groups[-1][0] if ch.isspace() and groups else next((i for i, f in enumerate(fs) if ord(ch) in f[3]), -1)
        if face < 0:  # decorative emoji, not part of the supported text scripts
            continue
        if groups and groups[-1][0] == face:
            groups[-1][1] += ch
        else:
            groups.append([face, ch])
    rtl = bool(re.match(r"^[^A-Za-z\u0900-\u097f]*[\u0600-\u06ff]", text))
    if rtl:
        groups.reverse()
    glyphs, pen = [], 0.0
    minx = miny = maxx = maxy = 0.0
    for face, raw in groups:
        font, hfont, unit, _, _ = fs[face]
        buf = hb.Buffer()
        buf.add_str(raw)
        buf.guess_segment_properties()
        buf.direction = "rtl" if face == 1 else "ltr"
        hb.shape(hfont, buf)
        cursor = 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            path, b = _path(face, font.getGlyphName(info.codepoint))
            x, y = pen + (cursor + pos.x_offset) / unit, pos.y_offset / unit
            glyphs.append((path, x, y, unit))
            minx, maxx = min(minx, x + b[0] / unit), max(maxx, x + b[2] / unit)
            miny, maxy = min(miny, y + b[1] / unit), max(maxy, y + b[3] / unit)
            cursor += pos.x_advance
        pen += cursor / unit
    return {"glyphs": glyphs, "minx": minx, "maxy": maxy, "width": max(maxx, pen) - minx,
            "height": maxy - miny or 1, "rtl": rtl}


def _lines(text, size, width, maximum):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}" if line else word
        if line and _shape(trial)["width"] * size > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines if len(lines) <= maximum else None


def text_box(text, box, size, color, max_lines=1, align="left"):
    original = str(text or "")
    x, y, w, h = box
    if not original or w <= 0 or h <= 0:
        return ""
    chosen = None
    fs = float(size)
    while fs >= 8:
        lines = _lines(original, fs, w, max_lines)
        if lines:
            shapes = [_shape(s) for s in lines]
            height = sum(s["height"] * fs for s in shapes) + max(0, len(lines) - 1) * fs * .45
            if all(s["width"] * fs <= w for s in shapes) and height <= h:
                chosen = lines, shapes, height
                break
        fs -= .5
    if not chosen:
        fs, short = max(8, min(size, h * .65)), original
        while len(short) > 1 and (_shape(short + "…")["width"] * fs > w or _shape(short + "…")["height"] * fs > h):
            short = short[:-1]
        shown = short if short == original else short + "…"
        s = _shape(shown)
        fs = min(fs, w / max(s["width"], .01), h / s["height"])
        chosen = [shown], [s], s["height"] * fs
    lines, shapes, height = chosen
    top, out = y + (h - height) / 2, []
    for line, s in zip(lines, shapes):
        left = x + ((w - s["width"] * fs) / 2 if align == "center" else w - s["width"] * fs if align == "right" or s["rtl"] else 0)
        baseline = top + s["maxy"] * fs
        paths = "".join(f'<path d="{path}" transform="translate({left + (gx-s["minx"])*fs:.6f} {baseline-gy*fs:.6f}) scale({fs/unit:.8f} {-fs/unit:.8f})"/>' for path, gx, gy, unit in s["glyphs"])
        bounds = ",".join(f"{z:.5f}" for z in (left, top, s["width"]*fs, s["height"]*fs))
        out.append(f'<g fill="{color}" role="img" aria-label="{html.escape(line)}" data-text="{html.escape(original)}" data-box="{bounds}"><title>{html.escape(line)}</title>{paths}</g>')
        top += s["height"] * fs + fs * .45
    return "".join(out)


def _ink(bg):
    rgb = [int(bg[i:i+2], 16) / 255 for i in (1, 3, 5)]
    rgb = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return "#000000" if sum(v*k for v, k in zip(rgb, (.2126, .7152, .0722))) > .179 else "#FFFFFF"


def _frame(w, h, label, body, layout):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(label)}" data-layout="{layout}"><title>{html.escape(label)}</title><metadata>Outlined text preserves shaping. Editable copy is in the text files. Small formats intentionally omit secondary content.</metadata>{body}</svg>'


def logo_data_uri(path, clients_dir=None):
    """Read only a validated client logo; never arbitrary filesystem paths."""
    from PIL import Image
    p = Path(path).resolve()
    if clients_dir is not None:
        try:
            p.relative_to(Path(clients_dir).resolve() / "logos")
        except ValueError:
            return ""
    if not p.is_file() or p.stat().st_size > 5_000_000:
        return ""
    with Image.open(p) as im:
        im.thumbnail((256, 256))
        buf = io.BytesIO()
        im.convert("RGBA").save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _image(logo, x, y, w, h):
    if not re.fullmatch(r"data:image/png;base64,[A-Za-z0-9+/]+={0,2}", logo or ""):
        return ""
    return f'<image href="{logo}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet" aria-label="Approved brand logo"/>'


def banner_svg(product, subtitle="", width=1200, height=630, primary="#E8B54A", secondary="#0F172A", cta="Learn more", logo="", **kwargs: Any):
    w, h = max(50, min(5000, int(width))), max(50, min(5000, int(height)))
    p = max(6, min(64, min(w, h)*.065))
    pc, sc = safe_hex(primary, "#E8B54A"), safe_hex(secondary, "#0F172A")
    subtitle = " · ".join(str(x) for x in kwargs.get("benefits",[])[:2]) or subtitle
    fg, label = _ink(sc), str(product or "Your brand")
    svg = f'<rect width="{w}" height="{h}" fill="{sc}"/><path d="M0 0H{w}" stroke="{pc}" stroke-width="{max(3,h*.007)}"/>'
    if pc == "#E8B54A" and sc == "#0F172A":
        svg += f'<circle cx="{w*.9}" cy="{h*.18}" r="{min(w,h)*.1}" fill="none" stroke="#3B82F6" stroke-opacity=".25"/>'
    if w < 180 and h < 120:
        layout = "micro"
        initials = "".join(word[0] for word in label.split()[:2])
        svg += _image(logo, p, p, w-2*p, h-2*p) if logo else text_box(initials, (p, p, w-2*p, h-2*p), min(w,h)*.5, fg, 1, "center")
    elif h < 120 and w > h*2:
        layout, lw, bw = "strip", h-2*p if logo else 0, min(145,w*.27)
        x = p + (lw+p if logo else 0)
        svg += _image(logo,p,p,lw,lw)+text_box(label,(x,p,w-x-bw-3*p,h-2*p),min(32,h*.39),fg,2)
        svg += f'<rect x="{w-p-bw}" y="{h*.23}" width="{bw}" height="{h*.54}" rx="{h*.10}" fill="{pc}"/>'
        svg += text_box(cta,(w-p-bw+6,h*.23+4,bw-12,h*.54-8),min(16,h*.25),_ink(pc),1,"center")
    else:
        layout = "vertical" if h>w*1.4 else "horizontal" if w>h*1.7 else "square"
        inner, hh = w-2*p, min(66,h*.13)
        lw = min(hh,inner*.25) if logo else 0
        benefits = [str(x).strip() for x in kwargs.get("benefits", []) if str(x or "").strip()]
        head = benefits[0] if benefits else ""
        title = head or label
        support = benefits[1] if len(benefits) > 1 else ""
        chips = benefits[2:][:2] if benefits else []
        rtl_t = head and _shape(title)["rtl"]
        # ── Art-direction kit (deterministic, procedural — mirrors Cloud engine) ──
        # 1. Layered glows, sheen and fine grain.
        svg += (f'<defs>'
          f'<radialGradient id="bfA" cx="82%" cy="18%" r="75%"><stop offset="0%" stop-color="{pc}" stop-opacity=".30"/><stop offset="55%" stop-color="{pc}" stop-opacity=".08"/><stop offset="100%" stop-color="{pc}" stop-opacity="0"/></radialGradient>'
          f'<radialGradient id="bfB" cx="8%" cy="95%" r="80%"><stop offset="0%" stop-color="{pc}" stop-opacity=".16"/><stop offset="60%" stop-color="{pc}" stop-opacity=".04"/><stop offset="100%" stop-color="{pc}" stop-opacity="0"/></radialGradient>'
          f'<linearGradient id="bfS" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="{fg}" stop-opacity=".05"/><stop offset="45%" stop-color="{fg}" stop-opacity="0"/></linearGradient>'
          f'<linearGradient id="bfScrim" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{sc}" stop-opacity="{".34" if fg=="#FFFFFF" else ".30"}"/><stop offset="64%" stop-color="{sc}" stop-opacity="0"/></linearGradient>'
          f'<filter id="bfG" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" stitchTiles="stitch" result="n"/><feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .04 0"/></filter></defs>'
          f'<rect width="{w}" height="{h}" fill="url(#bfA)"/><rect width="{w}" height="{h}" fill="url(#bfB)"/>'
          f'<polygon points="{w*.52:.5f},0 {w:.5f},0 {w:.5f},{h:.5f} {w*.52-h*.5:.5f},{h:.5f}" fill="{pc}" fill-opacity="{".055" if fg=="#FFFFFF" else ".09"}"/>'
          f'<rect width="{w}" height="{h}" fill="url(#bfS)"/>'
          f'<rect width="{w}" height="{h}" fill="url(#bfScrim)"/>'
          f'<rect width="{w}" height="{h}" filter="url(#bfG)" opacity=".55"/>')
        # 2. Stencil rings + dot grid in the accent.
        rmax = min(w,h)*.46
        for rr, oo in ((1,.22),(.72,.12),(.46,.07)):
            svg += f'<circle cx="{w:.5f}" cy="{h*.36:.5f}" r="{rmax*rr:.5f}" fill="none" stroke="{pc}" stroke-opacity="{oo}" stroke-width="{max(1,w*.0024):.5f}"/>'
        for i in range(5):
            for j in range(3):
                svg += f'<circle cx="{w*(.73+i*.048):.5f}" cy="{h*(.66+j*.1):.5f}" r="{max(1.3,w*.0024):.5f}" fill="{pc}" fill-opacity=".18"/>'
        # 3. Brand plate: monogram tile (or approved logo) + brand name + accent rule.
        tile_s = min(max(30, min(58, h*.082)), inner)
        fx = w-p-tile_s if rtl_t else p
        if logo:
            svg += _image(logo, p, p, lw, hh)
            name_x = p
        else:
            initials = "".join(wd[0] for wd in label.split() if re.match(r"\w", wd[0], flags=re.UNICODE))[:2] or "✷"
            svg += f'<rect x="{fx:.5f}" y="{p:.5f}" width="{tile_s:.5f}" height="{tile_s:.5f}" rx="{tile_s*.26:.5f}" fill="{pc}"/>'
            svg += text_box(initials, (fx, p+tile_s*.09, tile_s, tile_s*.82), tile_s*.46, _ink(pc), 1, "center")
            name_x = p if rtl_t else fx+tile_s+p*.42
        plate = str(kwargs.get("brand_text") or label)
        pbox = (p, p, max(1, w-p-tile_s-p*.42-p), tile_s) if rtl_t else (name_x, p+(tile_s-tile_s*.56)/2, max(1, w-p-name_x), tile_s*.56)
        svg += text_box(plate, pbox, min(21, w*.05, h*.06), fg, 1, "right" if rtl_t else "left")
        rule_w = max(90, w*.12)
        rx = w-p-rule_w if rtl_t else p
        svg += f'<rect x="{rx:.5f}" y="{p+tile_s+max(6,h*.012):.5f}" width="{rule_w:.5f}" height="{max(2,h*.006):.5f}" fill="{pc}" fill-opacity=".85"/>'
        # 4. Type block: benefit-led headline, support line with hairline rule, chips, CTA.
        svg += text_box(title, (p, max(p+tile_s+max(14,h*.03), h*.245), inner, h*.235), min(92, w*.10, h*.145), fg, 3, "right" if rtl_t else "left")
        if support:
            svg += f'<line x1="{w-p if rtl_t else p:.5f}" y1="{h*.505:.5f}" x2="{(w-p-max(70,w*.09)) if rtl_t else (p+max(70,w*.09)):.5f}" y2="{h*.505:.5f}" stroke="{pc}" stroke-width="{max(1.4,h*.004):.5f}" stroke-opacity=".8"/>'
            svg += text_box(support, (p, h*.515, inner, h*.085), min(25, w*.046), fg, 1, "right" if rtl_t else "left")
        if chips and not logo and h >= 320:
            chip_h = max(30, min(44, h*.07))
            cx = w-p if rtl_t else p
            for chip in chips:
                tw = _shape(chip)["width"] * 13.4 + p*.9 + 12
                if tw > inner*.46: continue
                x0 = cx-tw if rtl_t else cx
                svg += f'<rect x="{x0:.5f}" y="{h*.642:.5f}" width="{tw:.5f}" height="{chip_h:.5f}" rx="{chip_h/2:.5f}" fill="{fg}" fill-opacity="{".05" if fg=="#FFFFFF" else ".04"}" stroke="{pc}" stroke-opacity=".5" stroke-width="1"/>'
                svg += f'<circle cx="{x0+(tw-p*.62 if rtl_t else p*.62):.5f}" cy="{h*.642+chip_h/2:.5f}" r="{max(2,h*.006):.5f}" fill="{pc}"/>'
                svg += text_box(chip, (x0+p*.42+(0 if rtl_t else 8), h*.642+4, tw-p*1.1, chip_h-8), 13.4, fg, 1, "right" if rtl_t else "center")
                cx = cx-(tw+p*.5) if rtl_t else cx+tw+p*.5
        bw = min(inner*.62, max(100, w*.4)); bh = max(30, min(66, h*.112))
        by = h-p-bh-max(16, h*.028)
        cx0 = w-p-bw if rtl_t else p
        svg += f'<ellipse cx="{cx0+bw/2:.5f}" cy="{by+bh*.72:.5f}" rx="{bw*.55:.5f}" ry="{bh*.85:.5f}" fill="{pc}" fill-opacity=".16"/>'
        svg += f'<rect x="{cx0:.5f}" y="{by:.5f}" width="{bw:.5f}" height="{bh:.5f}" rx="{bh/2:.5f}" fill="{pc}"/>'
        svg += text_box(cta, (cx0+10, by+5, bw-20, bh-10), min(22, w*.048), _ink(pc), 1, "center")
    return _frame(w,h,label,svg,layout)


def logo_svg(brand, primary="#E8B54A", secondary="#0F172A", style="combination", **kwargs: Any):
    pc,sc = safe_hex(primary,"#E8B54A"),safe_hex(secondary,"#0F172A")
    fg,initials = _ink(sc),"".join(w[0] for w in str(brand).split()[:2])
    svg=f'<rect width="1024" height="1024" rx="64" fill="{sc}"/>'
    if style=="wordmark": svg+=text_box(brand,(80,290,864,440),150,fg,3,"center")
    elif style=="lettermark": svg+=f'<rect x="192" y="192" width="640" height="640" rx="170" fill="{pc}"/>'+text_box(initials,(242,290,540,400),320,_ink(pc),1,"center")
    elif style=="abstract": svg+=f'<path d="M260 250L650 150 810 470 500 580Z M214 560L460 654 734 536 740 820 320 850Z" fill="{pc}"/>'
    elif style=="pictorial": svg+=f'<path d="M260 710C180 290 600 190 780 210C800 660 520 830 260 710Z" fill="{pc}"/><path d="M270 735L630 375" stroke="{sc}" stroke-width="28" stroke-linecap="round"/>'
    elif style=="emblem": svg+=f'<circle cx="512" cy="490" r="335" fill="none" stroke="{pc}" stroke-width="22"/><circle cx="512" cy="490" r="290" fill="none" stroke="{pc}" stroke-width="3"/>'+text_box(initials,(295,265,434,250),220,fg,1,"center")+text_box(brand,(235,545,554,140),76,fg,2,"center")
    else: svg+=f'<circle cx="512" cy="338" r="165" fill="{pc}"/>'+text_box(initials,(385,230,254,210),145,_ink(pc),1,"center")+text_box(brand,(80,590,864,190),105,fg,2,"center")
    return _frame(1024,1024,str(brand),svg,"logo-"+style)
