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




# ---- Bold creative composition (premium agency review) — mirror of Cloud ----
# (cloud/api/_lib/visuals.js) one-for-one: calm field with radial-gradient
# washes and a board frame, one confident headline with a brand underline,
# ONE structured benefits area and a clean CTA row. Four deterministic layout
# personalities come from the brief hash, so different businesses get visibly
# different designs. Pass style "essential" for the calm classic layout.

def _h32(s):
    x = 5381
    for ch in str(s or ""):
        x = ((x * 33) ^ ord(ch)) & 0xFFFFFFFF
    return x


STAR_PATH = "M0 -1 L.22 -.22 1 0 .22 .22 0 1 -.22 .22 -1 0 -.22 -.22 Z"


PICTOS = [
    lambda c: f'<path d="{STAR_PATH}" transform="scale(11)" fill="{c}"/>',
    lambda c: f'<path d="M2.2 -11 L-6.5 2.4 h5.1 L-1.8 11 L8.5 -3.2 h-5.1 Z" fill="{c}"/>',
    lambda c: f'<path d="M-9 .5 L-3 6.5 L9 -6.5" fill="none" stroke="{c}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>',
    lambda c: f'<path d="M0 -11 L8 -8 V.5 C8 6.2 4.4 9.4 0 11 C-4.4 9.4 -8 6.2 -8 .5 V-8 Z" fill="{c}"/>',
    lambda c: f'<path d="M-8 9 C-8 -2 -2 -9 9 -9 C9 2 2 9 -8 9 Z" fill="{c}"/>',
    lambda c: (f'<g fill="{c}" stroke="{c}"><circle r="4.2" stroke="none"/>'
               f'<path d="M0 -11 v3 M0 8 v3 M-11 0 h3 M8 0 h3 M-7.8 -7.8 l2.1 2.1 M5.7 5.7 l2.1 2.1 M7.8 -7.8 L5.7 -5.7 M-5.7 5.7 l-2.1 2.1" fill="none" stroke-width="2.2" stroke-linecap="round"/></g>'),
]

_BOLD_DEFS = ('<defs><filter id="bfG" x="0" y="0" width="100%" height="100%">'
              '<feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" stitchTiles="stitch" result="n"/>'
              '<feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .04 0"/></filter></defs>')


def _bold_body(w, h, p, inner, head, sub, label, benefit_rows, offer, pc, sc, fg, rtl, logo, cta, layout, plate=""):
    # ----- Premium agency-ad composition (owner standard review, 2026-09-11) ---
    # Mirrors cloud/api/_lib/visuals.js one-for-one: calm field, one confident
    # headline with a brand underline, ONE structured benefits area and a clean
    # CTA row. Radial-gradient washes capped by the short canvas side, a fine
    # board frame, glass CTA and elevated cards. Four deterministic layout
    # personalities (hash of the brief); exact outlined text is never modified.
    H = _h32(label + "|" + head + "|" + "|".join(benefit_rows) + "|" + (offer or "")) or 1
    wide = layout == "horizontal" and w >= 760
    var_n = H % 4 if wide else H % 3
    ink_pc = _ink(pc)
    plate_txt = plate or label
    offer_txt = str(offer or "").strip()
    if offer_txt.isascii():
        offer_txt = offer_txt.upper()
    rows = [str(b) for b in benefit_rows if str(b or "").strip()][:3]
    initials = "".join(wd[0] for wd in label.split() if wd and wd[0].isalpha())[:2] or "✦"
    pad_x = p + (w * .01 if wide else w * .028)
    cont_x, cont_w = pad_x, w - 2 * pad_x
    tile_s = min(max(28, h * .075), 54, cont_w * .45)
    rtl_a = "right" if rtl else "left"
    L = cont_x + cont_w if rtl else cont_x
    R = cont_x if rtl else cont_x + cont_w
    wop = _ink(sc) == "#FFFFFF"  # dark board
    ink_bg_white = _ink(fg) == "#FFFFFF"
    mm = min(w, h)
    out = []

    # 1. Soft seeded atmosphere: radial-gradient washes with a soft falloff,
    # radii capped by the SHORT canvas side (balanced on tall formats), plus
    # a fine inset board frame.
    ws = 1 if H % 2 else -1
    sgn = -ws if rtl else ws
    w1_op = ".26" if wop else ".17"
    w2_op = ".14" if wop else ".09"
    out.append(
        f'<defs><radialGradient id="bfW1"><stop offset="0%" stop-color="{pc}" stop-opacity="{w1_op}"/>'
        f'<stop offset="100%" stop-color="{pc}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="bfW2"><stop offset="0%" stop-color="{pc}" stop-opacity="{w2_op}"/>'
        f'<stop offset="100%" stop-color="{pc}" stop-opacity="0"/></radialGradient></defs>'
        f'<ellipse cx="{R - sgn * w * .03:.6f}" cy="{h * .1:.6f}" rx="{mm * (.34 + (H % 5) * .012):.6f}" ry="{mm * .44:.6f}" fill="url(#bfW1)"/>'
        f'<ellipse cx="{L + sgn * w * .02:.6f}" cy="{h * .95:.6f}" rx="{mm * .3:.6f}" ry="{mm * .4:.6f}" fill="url(#bfW2)"/>'
        f'<rect x="{p * .6:.6f}" y="{p * .6:.6f}" width="{w - p * 1.2:.6f}" height="{h - p * 1.2:.6f}" rx="{p * .55:.6f}" fill="none" stroke="{fg}" stroke-opacity=".06" stroke-width="1.4"/>')

    head_y = p + tile_s + max(14, h * .034)
    bar_w = max(90, cont_w * .24)
    used_picts = set()

    def pict(b, i):
        # Seeded pick per benefit, salted by row index and deduped within the
        # banner so two benefits never share one mark.
        k = (_h32(str(b)) + i * 2) % len(PICTOS)
        while k in used_picts:
            k = (k + 1) % len(PICTOS)
        used_picts.add(k)
        return PICTOS[k]

    def icon_at(cx, cy, r, b, i):
        return f'<g transform="translate({cx:.6f} {cy:.6f}) scale({r / 11:.8f})">{pict(b, i)(pc)}</g>'

    def dot(cx, cy, c=None):
        return f'<circle cx="{cx:.6f}" cy="{cy:.6f}" r="{max(2.6, h * .006):.6f}" fill="{c or pc}"/>'

    def cta_pill(x, y, ph, pw):
        out.append(
            f'<ellipse cx="{x + pw / 2:.6f}" cy="{y + ph * .75:.6f}" rx="{pw * .56:.6f}" ry="{ph * .95:.6f}" fill="{pc}" fill-opacity=".18"/>'
            f'<rect x="{x:.6f}" y="{y:.6f}" width="{pw:.6f}" height="{ph:.6f}" rx="{ph / 2:.6f}" fill="{pc}"/>'
            f'<rect x="{x + ph * .3:.6f}" y="{y + ph * .09:.6f}" width="{max(1.0, pw - ph * .6):.6f}" height="{ph * .11:.6f}" rx="{ph * .055:.6f}" fill="{ink_pc}" fill-opacity=".22"/>'
            + text_box(cta, (x + 10, y + 5, pw - 20, ph - 10), min(22, w * .047), ink_pc, 1, "center"))

    # 2. Header: badge/logo at the reading edge, brand label beside it.
    bx = max(p * .6, R - tile_s) if rtl else L
    if logo:
        lw = min(tile_s * 1.9, cont_w * .3)
        out.append(_image(logo, bx, p, lw, tile_s))
    else:
        out.append(f'<rect x="{bx:.6f}" y="{p:.6f}" width="{tile_s:.6f}" height="{tile_s:.6f}" rx="{tile_s * .26:.6f}" fill="{pc}"/>')
        out.append(text_box(initials, (bx, p + tile_s * .09, tile_s, tile_s * .84), tile_s * .44, ink_pc, 1, "center"))
    lbl_w = cont_w * .44
    lbl_x = max(p, bx - p * .55 - lbl_w) if rtl else bx + tile_s * .7 + p * .5
    out.append(text_box(plate_txt, (lbl_x, p + tile_s * .1, lbl_w, tile_s * .8), min(22, w * .05, max(1, h * .058)), fg, 1, rtl_a))

    # 3. Offer chip at the far edge (glass stamp — never fights the badge).
    if offer_txt:
        chip_w, chip_h = min(cont_w * .3, 260), max(26, h * .05)
        cx0 = cont_x if rtl else cont_x + cont_w - chip_w
        chip_op = ".15" if ink_bg_white else ".1"
        out.append(
            f'<rect x="{cx0:.6f}" y="{p + tile_s * .14:.6f}" width="{chip_w:.6f}" height="{chip_h:.6f}" rx="{chip_h / 2:.6f}" fill="{pc}" fill-opacity="{chip_op}" stroke="{pc}" stroke-opacity=".5"/>')
        out.append(text_box(offer_txt, (cx0 + 8, p + tile_s * .14 + 3, chip_w - 16, chip_h - 6),
                            min(16, w * .034, max(1, h * .038)), pc, 1, "center"))

    def copy_block(bx0, bw2, t_h):
        # Headline + brand underline + sub line, reading-side aligned.
        out.append(text_box(head, (bx0, head_y, bw2, t_h), min(88, max(1, w * .078), max(1, h * .165)), fg, 2, rtl_a))
        by2 = head_y + t_h + max(10, h * .018)
        bar_h = max(4, h * .008)
        out.append(f'<rect x="{bx0 + bw2 - bar_w if rtl else bx0:.6f}" y="{by2:.6f}" width="{bar_w:.6f}" height="{bar_h:.6f}" rx="{bar_h / 2:.6f}" fill="{pc}"/>')
        y2 = by2 + max(10, h * .02)
        if sub:
            out.append(text_box(sub, (bx0, y2, bw2, h * .052), min(22, w * .042), fg, 1, rtl_a))
            y2 += h * .052 + max(8, h * .014)
        return y2

    if not wide:
        # ---- Personality A (square / tall / narrow): stacked composition ----
        pill_h = max(34, min(64, h * .1))
        pill_w = min(cont_w * .6, max(150, w * .42))
        pill_y = h - p - pill_h
        y2 = copy_block(cont_x, cont_w, min(h * .3, (pill_y - max(10, h * .02) - head_y) * .55))
        # Rail is centred in the zone between copy and CTA — on tall formats
        # this avoids a dead band under the benefits row.
        avail = max(0, pill_y - max(10, h * .014) - y2 - max(6, h * .012))
        rail_top = y2 + max(6, h * .012) + avail * .17
        rail_h = avail * .66
        if rows and rail_h > h * .1:
            m = len(rows)
            cw = cont_w / m
            i_r = min(rail_h * .2, cw * .16, max(1, h * .055))
            bub_op = ".13" if ink_bg_white else ".09"
            for i, b in enumerate(rows):
                cx = cont_x + cw * ((m - 1 - i) if rtl else i) + cw * .5
                out.append(f'<circle cx="{cx:.6f}" cy="{rail_top + i_r:.6f}" r="{i_r * 1.34:.6f}" fill="{pc}" fill-opacity="{bub_op}"/>')
                out.append(icon_at(cx, rail_top + i_r, i_r * 1.02, b, i))
                if i > 0:
                    dx = cont_x + cw * ((m - i) if rtl else i)
                    out.append(f'<rect x="{dx:.6f}" y="{rail_top + rail_h * .16:.6f}" width="1.2" height="{rail_h * .68:.6f}" fill="{fg}" fill-opacity=".13"/>')
                cap_h = max(14, rail_h - i_r * 2.34 - 4)
                out.append(text_box(b, (cx - cw * .44, rail_top + i_r * 2.34, cw * .88, cap_h), min(18, w * .038), fg, 3, "center"))
        cta_pill(R if rtl else R - pill_w, pill_y, pill_h, pill_w)
        return "".join(out)

    if var_n == 1:
        # ---- Personality B (wide): info card on the far side ----------------
        card_w = min(cont_w * .33, 370)
        gap2 = max(22, w * .026)
        card_x = cont_x if rtl else cont_x + cont_w - card_w
        bw2 = cont_w - card_w - gap2
        bx0 = card_x + card_w + gap2 if rtl else cont_x
        copy_block(bx0, bw2, h * .36)
        c_top = head_y
        c_bot = h - p - max(26, h * .048)
        rx = max(14, w * .016)
        sh_op = ".16" if wop else ".08"
        card_op = ".085" if ink_bg_white else ".055"
        out.append(
            f'<rect x="{card_x:.6f}" y="{c_top + max(7, h * .012):.6f}" width="{card_w:.6f}" height="{c_bot - c_top:.6f}" rx="{rx:.6f}" fill="#000000" fill-opacity="{sh_op}"/>'
            f'<rect x="{card_x:.6f}" y="{c_top:.6f}" width="{card_w:.6f}" height="{c_bot - c_top:.6f}" rx="{rx:.6f}" fill="{pc}" fill-opacity="{card_op}" stroke="{pc}" stroke-opacity=".42"/>')
        if rows:
            in_p = max(12, w * .013)
            row_h = (c_bot - c_top - 2 * in_p) / len(rows)
            for i, b in enumerate(rows):
                ry = c_top + in_p + i * row_h
                r_c = min(row_h * .3, 17)
                icx = card_x + card_w - in_p - r_c if rtl else card_x + in_p + r_c
                out.append(icon_at(icx, ry + row_h * .5, r_c, b, i))
                t_off = card_x + in_p if rtl else card_x + in_p + r_c * 2.4
                out.append(text_box(b, (t_off, ry, card_w - 2 * in_p - r_c * 2.4, row_h), min(17, w * .036), fg, 2, rtl_a))
                if i < len(rows) - 1:
                    out.append(f'<rect x="{card_x + in_p:.6f}" y="{ry + row_h:.6f}" width="{card_w - 2 * in_p:.6f}" height="1" fill="{fg}" fill-opacity=".12"/>')
        else:
            out.append(text_box(sub or plate_txt, (card_x + 12, c_top + 12, card_w - 24, c_bot - c_top - 24), min(18, w * .04), fg, 2, "center"))
        pill_h = max(34, min(60, h * .1))
        pill_w = min(bw2 * .66, max(150, w * .33))
        cta_pill(bx0, h - p - pill_h, pill_h, pill_w)
        return "".join(out)

    if var_n in (2, 3):
        # ---- Personality C/D (wide): solid primary panel --------------------
        panel_w = cont_w * .42
        gap2 = max(24, w * .028)
        flip = var_n == 3
        on_left = (not flip) if rtl else flip
        pan_x = cont_x if on_left else cont_x + cont_w - panel_w
        pan_top = head_y - tile_s * .32
        pan_bot = h - p - 4
        rxp = max(14, w * .018)
        psh_op = ".24" if wop else ".13"
        out.append(
            f'<rect x="{pan_x:.6f}" y="{pan_top + max(8, h * .014):.6f}" width="{panel_w:.6f}" height="{pan_bot - pan_top:.6f}" rx="{rxp:.6f}" fill="#000000" fill-opacity="{psh_op}"/>'
            f'<rect x="{pan_x:.6f}" y="{pan_top:.6f}" width="{panel_w:.6f}" height="{pan_bot - pan_top:.6f}" rx="{rxp:.6f}" fill="{pc}"/>')
        bw2 = cont_w - panel_w - gap2
        bx0 = cont_x + panel_w + gap2 if on_left else cont_x
        copy_block(bx0, bw2, h * .38)
        if rows:
            in_p = max(14, w * .016)
            row_h = (pan_bot - pan_top - 2 * in_p) / len(rows)
            for i, b in enumerate(rows):
                ry = pan_top + in_p + i * row_h
                dx = pan_x + panel_w - in_p - 8 if rtl else pan_x + in_p
                out.append(dot(dx, ry + row_h * .5, ink_pc))
                # RTL text ends before the dot zone; LTR text starts after it.
                t_x = pan_x + in_p if rtl else pan_x + in_p + 16
                out.append(text_box(b, (t_x, ry, panel_w - 2 * in_p - 16, row_h), min(19, w * .039), ink_pc, 2, rtl_a))
        else:
            out.append(text_box(sub or plate_txt, (pan_x + 16, pan_top + 16, panel_w - 32, pan_bot - pan_top - 32), min(19, w * .042), ink_pc, 2, "center"))
        pill_h = max(34, min(58, h * .095))
        pill_w = min(bw2 * .7, max(150, w * .3))
        cta_pill(bx0, h - p - pill_h, pill_h, pill_w)
        return "".join(out)

    # ---- Personality A-wide: headline above an icon rail --------------------
    pill_h = max(34, min(62, h * .1))
    pill_w = min(cont_w * .5, max(150, w * .38))
    pill_y = h - p - pill_h
    y2 = copy_block(cont_x, cont_w, min(h * .3, (pill_y - max(12, h * .02) - head_y) * .6))
    rail_top = y2 + max(8, h * .014)
    rail_h = pill_y - max(8, h * .012) - rail_top
    if rows and rail_h > h * .1:
        m = len(rows)
        cw = cont_w / m
        for i, b in enumerate(rows):
            cx = cont_x + cw * ((m - 1 - i) if rtl else i) + cw * .5
            i_r = min(rail_h * .26, cw * .14, max(1, h * .05))
            if i > 0:
                dx = cont_x + cw * ((m - i) if rtl else i)
                out.append(f'<rect x="{dx:.6f}" y="{rail_top + rail_h * .2:.6f}" width="1.2" height="{rail_h * .6:.6f}" fill="{fg}" fill-opacity=".13"/>')
            out.append(icon_at(cx, rail_top + i_r, i_r, b, i))
            cap_h = max(14, rail_h - i_r * 2.2 - 4)
            out.append(text_box(b, (cx - cw * .44, rail_top + i_r * 2.2, cw * .88, cap_h), min(17, w * .037), fg, 2, "center"))
    cta_pill(R if rtl else R - pill_w, pill_y, pill_h, pill_w)
    return "".join(out)


def banner_svg(product, subtitle="", width=1200, height=630, primary="#E8B54A", secondary="#0F172A", cta="Learn more", logo="", **kwargs: Any):
    w, h = max(50, min(5000, int(width))), max(50, min(5000, int(height)))
    p = max(6, min(64, min(w, h)*.065))
    pc, sc = safe_hex(primary, "#E8B54A"), safe_hex(secondary, "#0F172A")
    brief_subtitle = str(subtitle or "").strip()
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
        if kwargs.get("style", "bold") == "bold":
            # Copy split: the first benefit leads as the headline; real brief
            # text becomes the sub line when supplied (auto "For …" strings
            # and brand-name echoes are ignored). The benefits area gets the
            # REMAINING benefits, so no benefit is ever printed twice. With
            # enough benefits one also fills the sub line.
            brand_text = str(kwargs.get("brand_text") or label)
            sub_txt = brief_subtitle
            if sub_txt in (title, brand_text, f"For {brand_text}"):
                sub_txt = ""
            rest = [b for b in benefits if b != title]
            if not sub_txt and len(rest) > 2:
                sub_txt, rest = rest[0], rest[1:]
            rows = rest[:3]
            svg += _BOLD_DEFS + _bold_body(w, h, p, inner, title, sub_txt, label, rows,
                              str(kwargs.get("offer") or ""), pc, sc, fg, bool(_shape(title)["rtl"]), logo, cta,
                              layout, brand_text)
            svg += f'<rect width="{w}" height="{h}" filter="url(#bfG)" opacity=".45"/>'
            return _frame(w, h, label, svg, layout)
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
