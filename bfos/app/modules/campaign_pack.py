"""Transparent, client-ready campaign-pack documents."""

from __future__ import annotations

import csv
import html
import io
from datetime import datetime
from typing import Any, Dict


def _text(value: Any, limit: int = 6000) -> str:
    value = str(value or "")
    value = "".join(ch for ch in value if ch in "\n\r\t" or ord(ch) >= 32)
    return value[:limit]


def _benefits(value: Any):
    if isinstance(value, (list, tuple)):
        parts = [_text(item, 500).strip(" •-\t") for item in value]
    else:
        parts = [item.strip(" •-\t") for item in _text(value, 500).replace(";", ",").split(",")]
    return [item for item in parts if item][:4] or ["Your approved customer benefit"]


def _csv_cell(value: Any) -> str:
    """Keep spreadsheet formulas literal in customer-opened CSV files."""
    value = str(value or "")
    if value and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def build_campaign_pack(
    strategy: Dict[str, Any], copy_data: Dict[str, Any], analysis: Dict[str, Any], client_id: str
) -> Dict[str, str]:
    strategy = strategy if isinstance(strategy, dict) else {}
    copy_data = copy_data if isinstance(copy_data, dict) else {}
    analysis = analysis if isinstance(analysis, dict) else {}
    product = _text(strategy.get("product_name"), 80) or "Campaign"
    industry = _text(strategy.get("industry"), 80) or "General"
    audience = _text(strategy.get("target_audience"), 120) or "your audience"
    strategy_text = str(strategy.get("strategy_text") or "")
    copy_text = str(copy_data.get("copy_text") or "")
    if len(strategy_text)>30000 or len(copy_text)>30000:
        raise ValueError("Campaign pack content exceeds 30,000 characters per section")
    benefits = _benefits(copy_data.get("key_benefits", ""))
    quality = analysis.get("quality_score") if isinstance(analysis.get("quality_score"), dict) else {}
    claims = analysis.get("claim_review") if isinstance(analysis.get("claim_review"), dict) else {}
    now = datetime.now().strftime("%Y-%m-%d")
    agency_brand = _text(strategy.get("agency_brand"), 80) or "BRANDFORGE OS"
    agency_footer = _text(strategy.get("agency_footer"), 180)
    show_brandforge = bool(strategy.get("show_brandforge_branding", True))
    document_footer = agency_footer or agency_brand
    if show_brandforge and agency_brand != "BRANDFORGE OS":
        document_footer += " · Prepared with BrandForge OS"

    copy_pack = f"""# Copy Pack — {product}

**Audience:** {audience}
**Industry:** {industry}
**Prepared:** {now}

## Final campaign copy

{copy_text}

## Review reminder
Use only verified proof, approved offers, and claims your client can substantiate. Review platform, legal, and factual requirements before publication.
"""

    creative_brief = f"""# Creative Brief — {product}

## Objective
Turn the approved strategy into clear, brand-consistent campaign creative for {audience}.

## Approved customer benefits
""" + "\n".join(f"- {item}" for item in benefits) + f"""

## Visual direction
- Use the client’s saved primary and secondary brand colors.
- Keep the headline concise and the CTA visually obvious.
- Do not add unsupported statistics, awards, testimonials, prices, or before/after claims.
- Produce required channel sizes from the approved final copy.

## Strategy context
{strategy_text}
"""

    calendar = io.StringIO(newline="")
    writer = csv.writer(calendar)
    writer.writerow(["day", "channel", "content_angle", "approved_benefit", "cta", "review_status"])
    angles = ["Customer problem", "Approved benefit", "How it works", "Proof point", "Offer reminder", "FAQ", "Next step"]
    for day, angle in enumerate(angles, start=1):
        writer.writerow(
            [
                f"Day {day}",
                "Choose channel",
                angle,
                _csv_cell(benefits[(day - 1) % len(benefits)]),
                "Choose approved CTA",
                "Needs internal review",
            ]
        )

    warnings = claims.get("warnings") if isinstance(claims.get("warnings"), list) else []
    warning_items = "".join(
        f"<li>{html.escape(_text(item.get('message') if isinstance(item, dict) else item, 240))}</li>"
        for item in warnings
    ) or "<li>No Claim Guard rule matches found.</li>"
    next_steps = quality.get("next_steps") if isinstance(quality.get("next_steps"), list) else []
    next_items = "".join(f"<li>{html.escape(_text(item, 240))}</li>" for item in next_steps) or "<li>No automated improvement items.</li>"
    try:
        quality_value = max(0, min(100, int(float(quality.get("score") or 0))))
    except (TypeError, ValueError, OverflowError):
        quality_value = 0
    quality_status = _text(quality.get("status"), 80).replace("_", " ") or "needs revision"
    approval_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(product)} — Client Approval Summary</title>
<style>body{{font-family:Arial,sans-serif;background:#f6f7f9;color:#18202a;margin:0;padding:32px;line-height:1.5}}main{{max-width:820px;margin:auto;background:#fff;border:1px solid #dfe3e8;border-radius:16px;padding:36px}}.tag{{display:inline-block;padding:5px 10px;border-radius:999px;background:#fff5d9;color:#745000;font-size:12px;font-weight:700}}.score{{font-size:42px;font-weight:800}}section{{margin-top:26px;padding-top:20px;border-top:1px solid #e5e7eb}}h1{{margin:10px 0 4px}}h2{{font-size:17px}}pre{{white-space:pre-wrap;font:14px/1.6 Arial,sans-serif;background:#f7f8fa;padding:16px;border-radius:10px}}li{{margin:6px 0}}.note{{font-size:12px;color:#52606d}}</style></head>
<body><main><span class="tag">{html.escape(agency_brand)} · INTERNAL / CLIENT REVIEW</span><h1>{html.escape(product)}</h1><p>Campaign approval summary · {html.escape(industry)} · prepared {now}</p>
<section><h2>Campaign readiness</h2><div class="score">{quality_value}/100</div><p>{html.escape(quality_status.title())}</p><ul>{next_items}</ul></section>
<section><h2>Strategy</h2><pre>{html.escape(strategy_text)}</pre></section>
<section><h2>Final copy for review</h2><pre>{html.escape(copy_text)}</pre></section>
<section><h2>Claim Guard review</h2><ul>{warning_items}</ul><p class="note">Automated first pass only. The client and publisher must verify factual, legal, and platform compliance.</p></section>
<section><h2>Approval decision</h2><p>☐ Approved as written &nbsp;&nbsp; ☐ Changes requested &nbsp;&nbsp; ☐ Needs factual/compliance review</p><p>Reviewer: ____________________ &nbsp;&nbsp; Date: ____________________</p></section>
<p class="note">{html.escape(document_footer)}</p></main></body></html>"""

    return {
        "01_strategy_and_approval.html": approval_html,
        "02_copy_pack.md": copy_pack,
        "03_content_calendar.csv": calendar.getvalue(),
        "04_creative_brief.md": creative_brief,
        "README_DELIVERY.md": "# Campaign delivery\n\nReview the approval summary first, then adapt copy and creative assets only after client/factual approval. This pack is editable and can be printed to PDF from a browser.\n\n## Visual file formats\n\nEvery visual ships as SVG (the editable, infinitely scalable master) plus a pixel-perfect PNG twin at the same size — hero 1200\u00d7630, Instagram 1080\u00d71080, favicon 512, social avatar 500, every logo and custom banner at its requested size. The main ad placements (hero, Instagram) also include a JPEG twin, ready to upload to Meta/Google/LinkedIn. Missing PNGs? Run `pip install resvg-py` and regenerate the campaign.\n",
    }
