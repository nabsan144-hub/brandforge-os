#!/usr/bin/env python3
"""One-shot trust fix: regenerate pricing.html's FAQPage JSON-LD from the
visible FAQ markup so structured data never overstates what the page says.

Run: python3 scripts/sync_pricing_faq_jsonld.py
"""
import html
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
page_path = root / "sales" / "pricing.html"
page = page_path.read_text(encoding="utf-8")

# Locate the visible FAQ section (between the "Frequently asked" heading and
# the closing of its wrapper div).
start_marker = ">Frequently asked<"
start = page.index(start_marker)
end_marker = '</div>\n</div>\n<p class="text-center text-[11px]'
end = page.index(end_marker, start)
faq_html = page[start:end]

qas = []
for m in re.finditer(
    r'<h3 class="font-semibold mb-2 text-ink[^>]*>(.*?)</h3>\s*'
    r'<p class="text-\[13px\] text-muted leading-relaxed">(.*?)</p>',
    faq_html,
    re.S,
):
    def clean(part):
        part = re.sub(r"<[^>]+>", "", part)
        part = html.unescape(part)
        return re.sub(r"\s+", " ", part).strip()

    qas.append((clean(m.group(1)), clean(m.group(2))))

assert len(qas) == 10, f"expected 10 visible FAQ pairs, found {len(qas)}"

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

old_start = page.index('{"@context":"https://schema.org","@type":"FAQPage"')
# Replace through the closing of that JSON script tag.
old_end = page.index("\n</script>", old_start)
new_page = (
    page[:old_start]
    + block
    + page[old_end + 1 :]  # drop old content, keep the newline+</script>
)
json.loads(block)  # validate before writing
page_path.write_text(new_page, encoding="utf-8")
print(f"OK: synced FAQPage JSON-LD with {len(qas)} visible Q&As in sales/pricing.html")
