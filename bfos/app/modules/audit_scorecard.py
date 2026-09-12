"""
BrandForge OS - Audit Scorecard
Dynamic: real score from WebSearcher.seo_audit_html when a URL is audited;
ROI boxes computed from the founder's ACTUAL monthly spend. No hardcoded 72.
"""

import html
import math

from modules.security import safe_hex as _safe_hex  # noqa: E402
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from engines.ai_engine import AIEngine


class AuditScorecard:
    def __init__(self, ai_engine: "AIEngine" = None):
        self.ai = ai_engine

    def generate_scorecard_html(
        self,
        brand_name: str,
        url: str = "",
        industry: str = "General",
        primary_color: str = "#E8B54A",
        secondary_color: str = "#0F172A",
        site_audit: Optional[Dict[str, Any]] = None,
        monthly_spend: float = 200.0,
        brandforge_price: float = 199.0,
        brand_text: str = "BRANDFORGE OS",
    ) -> str:
        brand_name = html.escape((brand_name or "Your Brand")[:80])
        url = html.escape((url or "")[:200])
        industry = html.escape((industry or "General")[:80])
        pc = _safe_hex(primary_color, "#E8B54A")
        sc = _safe_hex(secondary_color, "#0F172A")
        badge = html.escape((brand_text or "").strip()[:24].upper() or "BRANDFORGE OS")

        # --- dynamic score ---
        site_audit = site_audit if isinstance(site_audit, dict) else {}
        score = site_audit.get("score")
        try:
            score_number = None if score is None else max(0, min(100, int(float(score))))
        except (TypeError, ValueError, OverflowError):
            score_number = None
        if score_number is None:
            score_line = '<div class="score">N/A</div><p style="color:#94A3B8;font-size:13px">No valid live audit score — run a URL audit for a measured card.</p>'
        else:
            score_line = f'<div class="score">{score_number}/100</div><p style="color:#94A3B8;font-size:13px">Rule-based page-check score, not a ranking forecast — method: {html.escape(str(site_audit.get("method", "static_html_analysis")))}</p>'

        checks = site_audit.get("checks") if isinstance(site_audit.get("checks"), dict) else {}
        check_items = ""
        if checks:
            labels = {
                "has_title": "Title tag", "title_length_ok": "Title length 30–65",
                "has_meta_description": "Meta description", "has_og_tags": "Open Graph",
                "has_canonical": "Canonical", "has_schema": "JSON-LD schema",
                "has_cta": "CTA present", "viewport_meta": "Mobile viewport",
            }
            for key, label in labels.items():
                if key in checks:
                    ok = checks[key]
                    result_color = "#10B981" if ok else "#F87171"
                    result_label = "pass" if ok else "fail"
                    check_items += (
                        '<div style="display:flex;justify-content:space-between;padding:6px 0;'
                        'border-bottom:1px solid rgba(255,255,255,0.06);font-size:13px">'
                        f'<span>{label}</span><b style="color:{result_color}">{result_label}</b></div>'
                    )

        # --- dynamic ROI math ---
        try:
            monthly = float(monthly_spend)
            if not math.isfinite(monthly) or monthly < 0 or monthly > 1_000_000:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            monthly = 200.0
        try:
            once = float(brandforge_price)
            if not math.isfinite(once) or once < 0 or once > 1_000_000:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            once = 199.0
        three_year = monthly * 36
        saving = three_year - once
        roi = (saving / once * 100) if once else 0
        payback = (once / monthly * 30) if monthly else 0
        # Honesty guard: at tiny spends the one-time tool doesn't pay back —
        # never render "You save -$13" on a client-facing scorecard.
        if saving > 0:
            saving_line = f"<span style=\"color:#10B981\">${saving:,.0f}</span>"
            saving_note = "in 3 years"
            roi_line = f"<span style=\"color:{pc}\">{roi:,.0f}%</span>"
            roi_note = f"Payback ~{payback:.0f} days"
        else:
            saving_line = "<span style=\"color:#94A3B8\">—</span>"
            saving_note = "doesn't pay back at this spend"
            roi_line = "<span style=\"color:#94A3B8\">—</span>"
            roi_note = "ownership removes lock-in"

        recs = site_audit.get("recommendations") if isinstance(site_audit.get("recommendations"), list) else []
        rec_items = "".join(f"<li>{html.escape(str(r)[:140])}</li>" for r in recs[:6]) or "<li>No recommendations were produced from these limited checks. This is not a complete SEO, accessibility or legal review.</li>"

        title_tag = str(site_audit.get("title") or "")[:90]
        title_line = f'<p class="sub" style="margin-top:-16px">Page title: {html.escape(title_tag)}</p>' if title_tag else ""

        if check_items:
            checklist_block = f"""<div style="margin-top:24px;padding:16px;background:rgba(255,255,255,0.03);border-radius:12px;border:1px solid #334155">
<h3 style="font-size:14px;font-weight:700;margin-bottom:8px">Checks observed on the fetched page</h3>
{check_items}
</div>"""
        else:
            checklist_block = ""

        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand_name} — Executive Audit Scorecard | BrandForge OS</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:system-ui;background:{sc};color:#F8FAFC;padding:24px}}
.card{{max-width:800px;margin:0 auto;background:#1E293B;border:1px solid #334155;border-radius:20px;padding:32px}}
.badge{{display:inline-block;background:{pc}26;color:{pc};border:1px solid {pc}66;padding:6px 12px;border-radius:9999px;font-size:11px;font-weight:700}}
h1{{font-size:28px;font-weight:800;margin:16px 0 8px}} .sub{{color:#94A3B8;font-size:14px;margin-bottom:24px}}
.score{{font-size:64px;font-weight:800;color:{pc}}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:24px}}
.box{{background:rgba(255,255,255,0.04);border:1px solid #334155;border-radius:12px;padding:16px}} .box b{{display:block;font-size:12px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.05em}} .box span{{font-size:20px;font-weight:700}}
.footer{{margin-top:32px;text-align:center;color:#64748B;font-size:11px}}
</style></head><body>
<div class="card">
<span class="badge">{badge} • EXECUTIVE AUDIT</span>
<h1>{brand_name} — Website Audit</h1>
<p class="sub">Industry: {industry} • URL: {url or 'N/A'}</p>
{score_line}{title_line}
<div class="grid"><div class="box"><b>Assumed monthly spend</b><span>${monthly:,.0f}/mo</span><small style="color:#94A3B8;display:block;font-size:11px">${three_year:,.0f} over 3 years</small></div>
<div class="box"><b>BrandForge OS</b><span style="color:{pc}">${once:,.0f} once</span><small style="color:#94A3B8;display:block;font-size:11px">Own forever, no subscriptions</small></div>
<div class="box"><b>You save</b>{saving_line}<small style="color:#94A3B8;display:block;font-size:11px">{saving_note}</small></div>
<div class="box"><b>Illustrative cost ratio</b>{roi_line}<small style="color:#94A3B8;display:block;font-size:11px">{roi_note}</small></div>
</div>
<p class="sub">Cost comparison assumes you replace the stated monthly spend. It excludes AI-provider fees, hosting, support, taxes and your time; these products may not replace the same tools. This is not measured business profit or return on investment.</p>
{checklist_block}
<div style="margin-top:24px;padding:16px;background:rgba(255,255,255,0.03);border-radius:12px;border:1px solid #334155">
<h3 style="font-size:14px;font-weight:700;margin-bottom:8px">Recommendations</h3>
<ul style="font-size:13px;color:#CBD5E1;line-height:1.6;margin-left:16px">{rec_items}</ul>
</div>
<div class="footer">Generated by {badge} • Local analysis of a public page</div>
</div>
</body></html>"""
