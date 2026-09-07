"""Portable, responsive draft landing/ad HTML using the approved brand assets."""
import base64
import html
import re
from functools import lru_cache
from urllib.parse import urlparse
from modules.visual_layout import FONT_DIR, _ink
from modules.security import safe_hex


@lru_cache(maxsize=3)
def _font(name):
    return base64.b64encode((FONT_DIR / f'{name}-Regular.ttf').read_bytes()).decode()


def landing_html(product, industry, audience, benefits, primary, secondary, cta='See details', url='', logo='', lang='en', compact=False):
    pc, sc = safe_hex(primary, '#E8B54A'), safe_hex(secondary, '#0F172A')
    fg, button = _ink(sc), _ink(pc)
    esc = lambda value: html.escape(str(value or ''), quote=True)
    href = url if urlparse(url).scheme in ('http','https') and not urlparse(url).username else '#details'
    font_css = ''
    for name, family in [('NotoSans','BrandLatin'),('NotoNaskhArabic','BrandArabic'),('NotoSansDevanagari','BrandHindi')]:
        if name == 'NotoSans' or (name == 'NotoNaskhArabic' and lang == 'ur') or (name == 'NotoSansDevanagari' and lang == 'hi'):
            font_css += f'@font-face{{font-family:{family};src:url(data:font/ttf;base64,{_font(name)}) format("truetype");font-display:swap;}}'
    logo_html = f'<img class="brand-logo" src="{logo}" alt="Approved brand logo">' if re.fullmatch(r'data:image/png;base64,[A-Za-z0-9+/]+={0,2}',logo or '') else ''
    items = ''.join(f'<li>{esc(b)}</li>' for b in benefits)
    title = esc(product)
    direction = 'rtl' if lang == 'ur' else 'ltr'
    # Supplied brief fields remain as entered in offline HTML; no fake translation.
    labels = {
      'en': ('For','Explore the details','Review draft — verify the offer, claims, consent and destination before publishing.'),
      'ur': ('کے لیے','تفصیلات دیکھیں','اشاعت سے پہلے پیشکش، دعووں، رضامندی اور لنکس کی تصدیق کریں۔'),
      'hi': ('के लिए','विवरण देखें','प्रकाशन से पहले प्रस्ताव, दावों, सहमति और लिंक की जाँच करें।'),
      'es': ('Para','Explora los detalles','Revisa la oferta, las afirmaciones, el consentimiento y los enlaces antes de publicar.'),
      'pt': ('Para','Explore os detalhes','Revise a oferta, as afirmações, o consentimento e os links antes de publicar.'),
    }.get(lang)
    if labels is None: labels = ('For','Explore the details','Review before publishing.')
    return f'''<!DOCTYPE html><html lang="{esc(lang)}" dir="{direction}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} — {esc(industry)}</title>
<meta name="description" content="{esc(product)}: {esc(', '.join(benefits))}"><style>{font_css}
*{{box-sizing:border-box}}body{{margin:0;background:{sc};color:{fg};font-family:BrandLatin,BrandArabic,BrandHindi,system-ui,sans-serif;line-height:1.65}}main{{max-width:{'560' if compact else '1040'}px;margin:auto;padding:clamp(20px,5vw,64px)}}header{{display:flex;gap:24px;align-items:center;flex-wrap:wrap;border-bottom:1px solid currentColor;padding-bottom:22px}}.brand-logo{{width:auto;height:auto;max-width:150px;max-height:80px;object-fit:contain}}header strong{{overflow-wrap:anywhere}}.hero{{padding:clamp(40px,8vw,94px) 0}}h1{{font-size:clamp(32px,6vw,72px);line-height:1.13;letter-spacing:-.035em;margin:0 0 24px;overflow-wrap:anywhere}}p{{max-width:60ch;overflow-wrap:anywhere}}.eyebrow{{font-size:14px;letter-spacing:.08em}}.cta{{display:inline-block;max-width:100%;background:{pc};color:{button};padding:14px 24px;border-radius:9px;text-decoration:underline;font-weight:bold;overflow-wrap:anywhere}}a:focus-visible{{outline:3px solid currentColor;outline-offset:5px}}#details{{border-top:1px solid currentColor;padding:24px 0}}ul{{padding-inline-start:24px}}li{{margin:12px 0;overflow-wrap:anywhere}}footer{{border-top:1px solid currentColor;padding-top:20px;font-size:13px}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto}}}}
</style></head><body><main class="card"><header>{logo_html}<strong>{title}</strong></header><section class="hero"><p class="eyebrow">{esc(industry)}</p><h1>{title}</h1><p>{esc(labels[0])} {esc(audience)}</p><p>{esc(benefits[0] if benefits else '')}</p><a class="cta" href="{esc(href)}">{esc(cta)}</a></section><section id="details"><h2>{esc(labels[1])}</h2><ul>{items}</ul></section><footer>{esc(labels[2])}</footer></main></body></html>'''
