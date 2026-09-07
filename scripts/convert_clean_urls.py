#!/usr/bin/env python3
"""Convert sales-site internal page links to clean URLs (Vercel cleanUrls).

The production site uses Vercel `cleanUrls: true`, so `pricing.html` is served
as `/pricing`. Canonical / og:url / JSON-LD url / internal <a> links still
pointed at the `.html` form, which 308-redirects — an extra hop and a
canonical-that-redirects mismatch. This rewrites the *page* links to the clean
form while leaving true filenames (ad_card.html, landing_page.html, the Google
verification file, assets) untouched.

Idempotent: only whitelisted page-name tokens are rewritten.

Usage:  python3 scripts/convert_clean_urls.py
"""
import glob
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SALES = ROOT / "sales"

# Page-name tokens (the real sales pages) -> their clean URL.
PAGES = ["agents", "workspace", "docs", "pricing",
         "tools", "demo", "privacy", "terms", "refund"]


def convert(text: str) -> str:
    # Rewrite navigation attributes only, never arbitrary text or artifact
    # filenames under assets/. External sites keep their own URL contracts.
    from urllib.parse import urlsplit, urlunsplit
    def link(match):
        prefix,quote,value=match.group(1),match.group(2),match.group(3)
        url=urlsplit(value)
        if url.netloc or url.scheme:
            return match.group(0)
        name=url.path.lstrip('/')
        if name=='index.html': path='/'
        elif name in {p+'.html' for p in PAGES}: path=url.path[:-5]
        else:return match.group(0)
        return prefix+quote+urlunsplit(('', '', path, url.query, url.fragment))+quote
    return re.sub(r"(\bhref=)([\"'])([^\"']+)\2",link,text)


def main() -> int:
    changed = []
    for f in sorted(glob.glob(str(SALES / "*.html"))):
        p = Path(f)
        original = p.read_text(encoding="utf-8")
        new = convert(original)
        if new != original:
            p.write_text(new, encoding="utf-8")
            changed.append(p.name)
    print(f"Clean-URL conversion applied to: {len(changed)} file(s).")
    for name in changed:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
