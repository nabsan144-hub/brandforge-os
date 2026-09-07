"""
BrandForge OS - 6-Agent Swarm Director — Marketing + High-End Design Focus

- Structured context flows to every agent (offline or online) — output is
  always about the USER's product.
- Each agent call carries an explicit `agent` intent so the offline engine
  routes deterministically.
- Market research is honest: real live results, or an explicit offline note.
- Campaign results carry client_id for white-label multi-client use;
  generated visuals carry the client's brand name (not a hardcoded badge).
- NEW: Full branding kit (logos, favicon, avatar, guidelines) + custom sizes
"""

import html
import logging
import re
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from modules.brand_planner import BrandPlanner
from modules.copywriter import Copywriter
from modules.visual_designer import VisualDesigner
from modules.claim_guard import review_marketing_copy
from modules.i18n import pick_lang as _pick_lang, t as _t
from modules.campaign_quality import score_campaign

if TYPE_CHECKING:
    from engines.ai_engine import AIEngine


from modules.security import safe_hex as _safe_hex, safe_text as _safe_text

log = logging.getLogger(__name__)


class SwarmDirector:
    def __init__(self, ai_engine: "AIEngine"):
        self.ai = ai_engine
        self.brand_planner = BrandPlanner(ai_engine)
        self.copywriter = Copywriter(ai_engine)
        self.designer = VisualDesigner(ai_engine)

    @staticmethod
    def _split_benefits(key_benefits: str) -> List[str]:
        if not key_benefits:
            return ["Quality you can verify", "Transparent pricing", "No fine print"]
        parts = re.split(r"[,;\n]+", key_benefits)
        seen, out = set(), []
        for p in parts:
            p = p.strip(" -•·	")[:60]
            if p and p.lower() not in seen:
                seen.add(p.lower())
                out.append(p)
            if len(out) >= 4:
                break
        return out or [key_benefits[:60]]

    def execute_swarm_campaign(self, product_name: str, industry: str, target_audience: str,
                               key_benefits: str, client_id: str = "default",
                               allow_ai_image: Optional[bool] = None,
                               custom_sizes: Optional[List[Dict[str, int]]] = None,
                               lang: str = "en", offer: str = "", cta: str = "", url: str = "",
                               generate_new_logo: bool = False) -> Dict[str, Any]:
        """Execute a full 6-stage campaign + branding kit + custom sizes.

        custom_sizes: optional list like [{"width": 300, "height": 250, "preset": "medium_rectangle"}, ...]
        If not provided, generates default hero 1200x630 + instagram 1080x1080.
        Branding kit always generated (logos, favicon, avatar, guidelines) — high-end design focus.
        """
        product_name = _safe_text(product_name, 80) or "Your Product"
        industry = _safe_text(industry, 80) or "General"
        target_audience = _safe_text(target_audience, 120) or "your customers"
        key_benefits = _safe_text(key_benefits, 500) or "Quality, transparent pricing"

        brand_brain = {
            "brand_promise": "", "proof_points": "", "prohibited_claims": "", "tone_of_voice": "",
            "agency_brand": "BRANDFORGE OS", "agency_footer": "", "show_brandforge_branding": True,
        }
        try:
            if getattr(self.ai, "clients", None):
                active = self.ai.clients.get_client(client_id) or self.ai.clients.get_active_client()
                brand_brain.update({
                    "brand_promise": _safe_text(active.get("brand_promise", ""), 240),
                    "proof_points": _safe_text(active.get("proof_points", ""), 500),
                    "prohibited_claims": _safe_text(active.get("prohibited_claims", ""), 300),
                    "tone_of_voice": _safe_text(active.get("tone_of_voice", ""), 80),
                    "agency_brand": _safe_text(active.get("agency_brand", "BRANDFORGE OS"), 80) or "BRANDFORGE OS",
                    "agency_footer": _safe_text(active.get("agency_footer", ""), 180),
                    "show_brandforge_branding": bool(active.get("show_brandforge_branding", True)),
                })
        except Exception:
            pass
        brand_rules = (
            f"Brand promise: {brand_brain['brand_promise'] or 'Not supplied'}\n"
            f"Approved proof points: {brand_brain['proof_points'] or 'Not supplied — do not invent proof'}\n"
            f"Prohibited claims/phrases: {brand_brain['prohibited_claims'] or 'None supplied'}\n"
            f"Voice: {brand_brain['tone_of_voice'] or 'Use a clear, professional voice'}"
        )
        lang = _pick_lang(lang)
        context = {
            "product": product_name,
            "industry": industry,
            "target_audience": target_audience,
            "lang": lang,
            "key_benefits": key_benefits,
            "brand_rules": brand_rules,
            "tone": brand_brain["tone_of_voice"], "proof": brand_brain["proof_points"],
            "avoided": brand_brain["prohibited_claims"], "offer": offer, "cta": cta, "url": url,
        }

        def _ctx(agent: str) -> Dict[str, str]:
            c = dict(context)
            c["agent"] = agent
            return c

        # Agent 5: Market Researcher — live search only when online provider
        research_text = "Live web research unavailable in offline mode — no trend data was fabricated."
        research_live = False
        provider = getattr(self.ai, "provider", "offline")
        try:
            online_connected = provider not in ("offline", "ollama") and bool(self.ai.has_key(provider))
        except Exception:
            online_connected = False
        if online_connected:
            try:
                if getattr(self.ai, "searcher", None):
                    results = self.ai.searcher.search(f"{industry} {product_name} trends", max_results=3)
                    if results:
                        research_live = True
                        research_text = self.ai.searcher.format_search_summary(f"{industry} trends", results)[:1200]
                    else:
                        research_text = ("Live web search unavailable (network-limited) — this campaign "
                                         "contains no live trend data.")
            except Exception:
                research_text = "Live web search unavailable (network-limited) — no live trend data in this campaign."

        # Agent 1: Brand Strategist
        try:
            strat_prompt = (
                f"Chief Brand Strategist engagement.\n"
                f"Product: {product_name}\nIndustry: {industry}\nTarget: {target_audience}\n"
                f"Benefits: {key_benefits}\nBrand rules:\n{brand_rules}\n"
                f"{'Research: ' + research_text[:600] if research_text else 'No live research (offline mode).'}\n\n"
                "Deliver: 1. Positioning (1 sentence) 2. Archetype & Tone 3. 3 Pain points 4. Color direction. "
                "Be specific and bold. Write ONLY about this product and its market."
            )
            strategy_text = self.ai.generate_text(
                strat_prompt,
                system_prompt="You are an elite CMO, ex-Apple. Be specific, no fluff.",
                max_tokens=800, context=_ctx("strategist"), client_id=client_id,
            )
        except Exception:
            b1 = self._split_benefits(key_benefits)[0]
            strategy_text = (f"Positioning: For {target_audience} who want {b1}, {product_name} is the "
                             f"{industry} option that verifies before it promises. Archetype: Sage + Creator.")

        # Agent 2: Copywriter
        try:
            copy_prompt = (
                f"Direct-response copy engagement.\nProduct: {product_name}\nIndustry: {industry}\n"
                f"Audience: {target_audience}\nBenefits: {key_benefits}\nBrand rules:\n{brand_rules}\nStrategy: {strategy_text[:500]}\n\n"
                "Write: 1. AIDA ad (bold hook) 2. PAS LinkedIn post + hashtags 3. Welcome email "
                "(subject/preheader/body ~150 words) 4. Landing hero headline/sub/CTA. Bold, authoritative, specific."
            )
            draft_copy = self.ai.generate_text(
                copy_prompt,
                system_prompt="You are a world-class direct-response copywriter. Write ads that sell — specific, honest, no fabricated claims.",
                max_tokens=1200, context=_ctx("copywriter"), client_id=client_id,
            )
        except Exception:
            bens = self._split_benefits(key_benefits)
            draft_copy = (f"AIDA: Attention — {target_audience} still choosing the hard way? "
                          f"Interest — {product_name}: {', '.join(bens[:2])}. "
                          f"Desire — verify before you commit. Action — get started.\n"
                          f"PAS: Problem — overpromising {industry} options. Agitate — the cost of a bad pick "
                          f"outlives the invoice. Solution — {product_name}, {bens[0]}.")

        # Agent 3: Quality Sentinel
        try:
            verify_prompt = (
                f"Quality Sentinel pass — tighten this copy for {product_name}.\n"
                "Score: hook strength, fluff removal, consistency. Return ONLY the final refined copy, "
                "preserving EVERY section, fact, price, link and CTA. Do not add claims.\n\nDRAFT:\n" + draft_copy
            )
            refined_copy = self.ai.generate_text(
                verify_prompt,
                system_prompt="You are a careful editor. Keep the complete requested deliverable. Preserve all facts and sections.",
                max_tokens=min(8000, max(1800, len(draft_copy) // 2)), context=_ctx("sentinel"), client_id=client_id,
            )
        except Exception:
            refined_copy = draft_copy

        from modules.draft_integrity import preserves_draft
        refinement_preserved = preserves_draft(draft_copy, refined_copy)
        if not refinement_preserved:
            refined_copy = draft_copy

        # Agent 4: Visual Architect — now with branding kit + custom sizes
        primary, secondary, brand_text = "#E8B54A", "#0F172A", "BRANDFORGE OS"
        try:
            if getattr(self.ai, "clients", None):
                active = self.ai.clients.get_client(client_id) or self.ai.clients.get_active_client()
                from modules.visual_layout import logo_data_uri
                if active.get("logo_path"):
                    self.designer.approved_logo = logo_data_uri(active["logo_path"], self.ai.clients.clients_dir)
                primary = _safe_hex(active.get("primary_color") or primary, primary)
                secondary = _safe_hex(active.get("secondary_color") or secondary, secondary)
                brand_text = _safe_text(active.get("agency_brand") or "BRANDFORGE OS", 40) or "BRANDFORGE OS"
        except Exception:
            pass

        # White-label honesty: when no client/agency brand is configured, the
        # deliverables carry the CAMPAIGN's own product name — never a
        # BrandForge vendor badge (matches the documented "not a vendor badge"
        # behavior; the vendor name only appears when an agency chooses it).
        if brand_text == "BRANDFORGE OS":
            brand_text = _safe_text(product_name, 40) or "BrandForge"

        self.designer.campaign_lang = lang
        self.designer.campaign_url = url
        self.designer.campaign_cta = cta or _t(lang, "svgCta")
        benefits = self._split_benefits(key_benefits)
        svg_for = _t(lang, "svgFor")
        try:
            hero_svg = self.designer.generate_hero_banner_svg(
                product_name, f"{svg_for} {target_audience}", cta_text=cta or _t(lang, "svgCta"),
                primary_color=primary, secondary_color=secondary,
                brand_text=brand_text, benefits=benefits)
        except Exception:
            hero_svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='630'><text>{html.escape(product_name)}</text></svg>"
        try:
            insta_svg = self.designer.generate_instagram_square_svg(
                product_name, benefits[0] if benefits else "Built different",
                primary_color=primary, secondary_color=secondary,
                brand_text=brand_text, benefits=benefits)
        except Exception:
            insta_svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='1080' height='1080'><text>{html.escape(product_name)}</text></svg>"
        try:
            ad_html = self.designer.generate_html_ad_card(
                product_name, f"Built for {target_audience}.", benefits,
                primary_color=primary, secondary_color=secondary, brand_text=brand_text)
        except Exception:
            ad_html = f"<html><body><h1>{html.escape(product_name)}</h1></body></html>"
        try:
            landing_html = self.designer.generate_landing_page(
                product_name, industry, target_audience, benefits,
                cta_text=cta or _t(lang, "svgCta"), primary_color=primary, secondary_color=secondary,
                brand_text=brand_text, cta_url=url or "#start")
        except Exception:
            landing_html = ""

        # NEW: Branding kit — logos etc. — high-end design focus
        branding_files: Dict[str, str] = {}
        try:
            # Use product_name as brand for kit (or agency_brand if available)
            kit_brand = product_name
            branding_files = self.designer.generate_branding_kit(
                kit_brand, primary, secondary, industry, f"{kit_brand} — {industry}"
            )
        except Exception:
            branding_files = {}

        approved_logo = getattr(self.designer, "approved_logo", "")
        if approved_logo and not generate_new_logo:
            branding_files = {**{k:v for k,v in branding_files.items() if k in ("color_palette.json","brand_guidelines.md")}, "approved_logo.svg": (
                '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
                f'<image href="{approved_logo}" width="512" height="512" preserveAspectRatio="xMidYMid meet"/></svg>'
            )}

        # NEW: Custom sizes — if user requested specific ad sizes
        custom_banner_files: Dict[str, str] = {}
        try:
            if custom_sizes and isinstance(custom_sizes, list):
                for item in custom_sizes[:21]:  # API validates the 21-per-run ceiling
                    if not isinstance(item, dict):
                        continue
                    w = item.get("width", 300)
                    h = item.get("height", 250)
                    preset = str(item.get("preset", ""))[:30]
                    try:
                        w, h = int(w), int(h)
                        w = max(50, min(w, 5000))
                        h = max(50, min(h, 5000))
                    except (TypeError, ValueError) as exc:
                        log.debug("swarm banner: skipping item with bad size %r (%s)", item.get("width"), exc)
                        continue
                    # Generate custom banner
                    try:
                        svg = self.designer.generate_ad_banner_svg(
                            product_name, w, h, primary, secondary, brand_text, benefits, cta_text=cta or _t(lang, "svgCta"), preset=preset
                        )
                        fname = f"banner_{preset or f'{w}x{h}'}.svg"
                        # Ensure safe filename
                        fname = re.sub(r"[^a-zA-Z0-9._-]", "_", fname)[:80]
                        custom_banner_files[fname] = svg
                    except Exception:
                        continue
        except Exception:
            custom_banner_files = {}

        # Agent 6: SEO & ROI Analyst
        try:
            seo_prompt = (
                f"SEO and conversion suggestions for {product_name}.\nCopy:\n{refined_copy[:6000]}\n"
                "No live page was audited. Do not provide an SEO score, invented keyword volumes, rankings or ROI. "
                "Give keyword seeds, useful on-page suggestions, and a measurement plan. Label assumptions."
            )
            seo_analysis = self.ai.generate_text(
                seo_prompt,
                system_prompt="You are a data-driven SEO + CRO expert.",
                max_tokens=700, context=_ctx("seo"), client_id=client_id,
            )
        except Exception:
            from modules.fallback_copy import fallback
            seo_analysis = fallback("seo", context, lang)

        # Persist insight to memory
        try:
            if getattr(self.ai, "memory", None):
                self.ai.memory.save_campaign_insight(
                    f"{product_name} Campaign", product_name,
                    f"{industry}, {target_audience}, {key_benefits[:100]}", client_id=client_id)
        except Exception:
            pass

        claim_review = review_marketing_copy(refined_copy, brand_brain["prohibited_claims"])
        quality_score = score_campaign(
            refined_copy, brand_brain["brand_promise"], brand_brain["proof_points"], claim_review
        )

        visual_files = {
            "hero_banner.svg": hero_svg,
            "instagram_square.svg": insta_svg,
            "ad_card.html": ad_html,
        }
        if landing_html:
            visual_files["landing_page.html"] = landing_html

        # Add branding kit files (logos etc.)
        if branding_files:
            # Prefix branding files to avoid collision
            for k, v in branding_files.items():
                # Keep branding files separate but included in campaign deliverables
                # e.g. branding/primary_logo.svg
                visual_files[f"branding/{k}"] = v

        # Add custom size banners
        if custom_banner_files:
            visual_files.update(custom_banner_files)

        # PNG/JPEG raster export — ad platforms (Meta/Google/LinkedIn) accept
        # PNG/JPEG, not SVG. The SVG stays the editable master; resvg renders
        # the pixel twin. Degrades honestly to SVG-only if resvg is missing.
        png_export_status = "ok"
        try:
            from modules.image_export import export_visual_rasters, PNG_EXPORT_AVAILABLE
            if PNG_EXPORT_AVAILABLE:
                visual_files.update(export_visual_rasters(visual_files))
            else:
                png_export_status = "unavailable (pip install resvg-py)"
        except Exception:
            png_export_status = "error"

        # Brand-aware AI image design. Quality providers (Gemini / Grok /
        # OpenAI, via the user's API keys) generate the brand photo; the
        # compositor lays the brand typography on top and resvg renders the
        # final PNG/JPEG. Offline promise intact: no network call unless an
        # image API key exists OR the campaign is already online. Any
        # failure keeps the deterministic SVG deliverables above.
        ai_image_used = False
        ai_image_provider = None
        try:
            if allow_ai_image is not False:
                from modules.ai_image_designer import AIImageDesigner
                image_ai = AIImageDesigner(ai_engine=self.ai)
                # Offline campaigns stay fully offline (auto mode); an
                # explicitly chosen image provider is the user's opt-in.
                may_call_network = image_ai.network_allowed(online_connected)
                if may_call_network:
                    svg_for = _t(lang, "svgFor")
                    cta_label = _t(lang, "svgCta")
                    for kind, w, h in (("hero", 1200, 630), ("square", 1080, 1080)):
                        shot = image_ai.generate_design_image(
                            product_name=product_name, industry=industry,
                            target_audience=target_audience, benefits=benefits,
                            primary_color=primary, secondary_color=secondary,
                            width=w, height=h, allow_network=online_connected,
                        )
                        if not shot or not shot.get("bytes"):
                            continue
                        raw = shot["bytes"]
                        if kind == "hero":
                            visual_files["hero_image.jpg"] = raw
                        else:
                            visual_files["instagram_image.jpg"] = raw
                        ai_image_used = True
                        ai_image_provider = shot.get("provider") or ai_image_provider
                        # Compose the brand design over the photo and render
                        # raster deliverables (PNG + JPEG).
                        try:
                            from modules.image_export import svg_to_png_bytes, png_bytes_to_jpeg_bytes
                            if kind == "hero":
                                comp = self.designer.generate_photo_hero_svg(
                                    raw, product_name,
                                    f"{svg_for} {target_audience}",
                                    primary_color=primary, secondary_color=secondary,
                                    brand_text=brand_text, benefits=benefits,
                                    cta_text=cta_label, width=w, height=h)
                            else:
                                comp = self.designer.generate_photo_square_svg(
                                    raw, product_name, benefits[0] if benefits else "Built different",
                                    primary_color=primary, secondary_color=secondary,
                                    brand_text=brand_text, benefits=benefits,
                                    cta_text=cta_label, width=w, height=h)
                            png = svg_to_png_bytes(comp)
                            suffix = "hero_ai" if kind == "hero" else "instagram_ai"
                            visual_files[suffix + ".png"] = png
                            try:
                                visual_files[suffix + ".jpg"] = png_bytes_to_jpeg_bytes(png)
                            except Exception:
                                pass  # PNG twin is enough; JPEG is a bonus
                        except Exception:
                            pass  # raw photo already saved; template visuals remain
        except Exception:
            ai_image_used = ai_image_used

        actual_provider = getattr(self.ai, "last_provider", provider)
        return {
            "strategy_data": {
                "product_name": product_name, "approved_logo": approved_logo, "offer": offer, "cta": cta, "url": url,
                "industry": industry,
                "target_audience": target_audience,
                "strategy_text": strategy_text,
                "market_research": research_text,
                "research_live": research_live,
                "provider": actual_provider,
                "agency_brand": brand_brain["agency_brand"],
                "agency_footer": brand_brain["agency_footer"],
                "show_brandforge_branding": brand_brain["show_brandforge_branding"],
                "color_palette": [
                    {"name": "Primary", "hex": primary, "role": "Premium CTA"},
                    {"name": "Secondary", "hex": secondary, "role": "Trust"},
                    {"name": "Action", "hex": "#10B981", "role": "Action"},
                ],
            },
            "copy_data": {
                "product_name": product_name,
                "key_benefits": key_benefits,
                "copy_text": refined_copy, "refinement_preserved": refinement_preserved,
                "draft_copy": draft_copy,
            },
            "visual_files": visual_files,
            "png_export_status": png_export_status,
            "analysis_data": {
                "seo_analysis": seo_analysis,
                "benefits_list": benefits,
                "claim_review": claim_review,
                "quality_score": quality_score,
            },
            "meta": {
                "client_id": client_id,
                "lang": lang,
                "provider": actual_provider,
                "research_live": research_live,
                "ai_image": ai_image_used,
                "image_provider": ai_image_provider,
                "branding_kit": bool(branding_files),
                "custom_sizes": len(custom_banner_files),
            },
        }
