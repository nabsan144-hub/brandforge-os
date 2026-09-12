#!/usr/bin/env python3
"""
Regenerate sales/sitemap.xml with `lastmod` dates pulled from git history.

Keeps the sitemap from drifting: instead of hand-editing `lastmod`, this reads
the last Commit Date of each page file (falling back to today for a file that
isn't in the current checkout's history, e.g. new/untracked files).

Usage:
  python3 scripts/regenerate_sitemap.py
"""
import subprocess
import sys
import re
from xml.sax.saxutils import escape
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SALES = ROOT / "sales"
OUT = SALES / "sitemap.xml"

# page file -> (priority, loc path). Order preserved from the existing sitemap.
# The site serves with Vercel `cleanUrls: true`, so the canonical loc is the
# clean URL (no .html) — matches the clean canonical/og tags in the pages.
# Include every indexable root page; never silently drop comparison guides
# when regenerating a hard-coded list. Private/draft pages must opt out.
PAGES = []
for page in sorted(SALES.glob('*.html')):
    text = page.read_text(encoding='utf-8')
    if page.name == '404.html' or re.search(r'<meta[^>]+name=[\'"]robots[\'"][^>]+content=[\'"][^\'"]*noindex', text, re.I):
        continue
    PAGES.append((page.name, '1.0' if page.name == 'index.html' else '0.6', '/' if page.name == 'index.html' else '/' + page.stem))


# The site serves at www.brandforge-os.com (the non-www host 308-redirects to
# it), so the canonical host is www. Keep sitemap URLs on www to match the
# canonical/og:url tags baked into the pages.
_config = (SALES/'assets/config.js').read_text(encoding='utf-8')
_match = re.search(r"site_url:\s*['\"]([^'\"]+)['\"]", _config)
SITE_URL = _match.group(1).rstrip('/') if _match else 'https://www.brandforge-os.com'
ALTERNATE = "https://brandforge-os.com"


def lastmod_for(rel: Path) -> str:
    """Last date a page was committed (YYYY-MM-DD); fall back to today."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(rel)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        if out:
            return out
    except (subprocess.SubprocessError, OSError):
        pass
    return date.today().isoformat()


def main() -> int:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page, priority, loc in PAGES:
        lastmod = lastmod_for(rel=SALES / page)
        lines.append(
            f"  <url><loc>{escape(SITE_URL+loc)}</loc><lastmod>{lastmod}</lastmod>"
            f"<priority>{priority}</priority></url>"
        )
    lines.append("</urlset>")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(PAGES)} URLs, dates from git history).")
    for page, _, loc in PAGES:
        print(f"  {loc:<18} {lastmod_for(SALES / page)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
