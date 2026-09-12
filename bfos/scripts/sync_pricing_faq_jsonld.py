#!/usr/bin/env python3
"""Trust gate: regenerate pricing.html's FAQPage JSON-LD from the visible
FAQ markup so structured data never overstates what the page says. Fails
loudly (non-zero) when the visible FAQ and the JSON-LD drift apart.

Run: python3 scripts/sync_pricing_faq_jsonld.py
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
page_path = root / "sales" / "pricing.html"
page = page_path.read_text(encoding="utf-8")

# Visible FAQ = every <details> block inside the #faq section. Locate that
# section by its stable id, not by heading wording or surrounding divs.
section_start = page.index('id="faq"')
section = page[section_start:]
details = section.split("</details>")[:-1]


def clean(part):
    part = re.sub(r"<[^>]+>", "", part)
    part = html.unescape(part)
    return re.sub(r"\s+", " ", part).strip()


qas = []
for block in details:
    m = re.search(
        r"<summary[^>]*>(.*?)</summary>.*?<p[^>]*>(.*?)</p>", block, re.S
    )
    if not m:
        raise SystemExit("FAQ <details> block without summary+answer paragraph — markup drifted")
    qas.append((clean(m.group(1)), clean(m.group(2))))

assert len(qas) == 10, f"expected 10 visible FAQ pairs, found {len(qas)}"
assert all(q and a for q, a in qas), "empty question or answer in visible FAQ"

entity = [
    {
        "@type": "Question",
        "name": q,
        "acceptedAnswer": {"@type": "Answer", "text": a},
    }
    for q, a in qas
]
block = json.dumps(
    {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entity},
    ensure_ascii=False,
    indent=1,
)

# Replace the FIRST FAQPage standalone block (prettier- or compact-printed).
m = re.search(
    r'\{\s*"@context":\s*"https://schema\.org"\s*,\s*"@type":\s*"FAQPage"',
    page,
)
if not m:
    raise SystemExit("FAQPage JSON-LD block not found in sales/pricing.html")
old_start = m.start()
script_open = page.rindex("<script", 0, old_start)
Script_close = "</script>"
script_end = page.index(Script_close, old_start)
new_page = page[: script_open + page[script_open:].index(">") + 1] + "\n" + block + "\n" + page[script_end:]
json.loads(block)  # validate before writing
page_path.write_text(new_page, encoding="utf-8")
print(f"OK: synced FAQPage JSON-LD with {len(qas)} visible Q&As in sales/pricing.html")

# Trust gate: the file must not differ from HEAD after the sync — a diff
# means copy was edited without re-running this tool or hand-edited JSON-LD.
if "--assert-clean" in sys.argv[1:]:
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", str(page_path)],
        cwd=root,
    )
    if dirty.returncode:
        raise SystemExit(
            "FAQPage JSON-LD differs from visible FAQ (git diff after sync) — "
            "do not hand-edit structured data; edit the visible FAQ and re-run this tool."
        )
    print("OK: FAQPage JSON-LD matches visible FAQ")
