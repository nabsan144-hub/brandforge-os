"""
BrandForge OS - Tool Registry — 21 real tools (marketing + high-end design focus)
Security: input validation, timeouts, safe file ops.
NEW: branding kit + custom size + logo generation
"""

import json
import logging
import math
import os
from modules.runtime_paths import data_dir as default_data_dir
import re
from typing import Dict, Any, List, Callable

from modules.security import atomic_write_bytes, atomic_write_text, safe_slug as _safe_slug_base, safe_text as _clean_text

log = logging.getLogger(__name__)


def _safe_slug(name: str, max_len: int = 60) -> str:
    return _safe_slug_base(name, max_len, lower=False)


def _safe_path(base: str, rel: str) -> str:
    safe_rel = _safe_slug(rel.replace('/', '_').replace('\\', '_'), 100)
    full = os.path.join(base, safe_rel)
    base_abs = os.path.abspath(base)
    full_abs = os.path.abspath(full)
    if os.path.commonpath([base_abs, full_abs]) != base_abs:
        raise ValueError("Path traversal blocked")
    return full


class MCPRegistry:
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or default_data_dir()
        self.output_dir = os.path.join(self.base_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._searcher = None
        self._memory = None
        self._register_all_tools()

    def _get_searcher(self):
        if self._searcher is None:
            from modules.web_searcher import WebSearcher
            self._searcher = WebSearcher(data_dir=self.base_dir)
        return self._searcher

    def _get_memory(self):
        if self._memory is None:
            from modules.memory_manager import MemoryManager
            self._memory = MemoryManager(base_dir=self.base_dir)
        return self._memory

    def _active_client_id(self) -> str:
        try:
            from modules.client_manager import ClientManager
            active = ClientManager(base_dir=self.base_dir).get_active_client()
            return str(active.get("client_id") or "default")[:40]
        except Exception:
            return "default"

    def _register_all_tools(self):
        # Research & audit (4)
        self.register("web_search", "Live web search. Returns real results or empty if offline — never fabricated.", self._tool_web_search, {"query": "string"})
        self.register("inspect_url", "Fetch a competitor/public URL and extract readable text", self._tool_inspect_url, {"url": "string"})
        self.register("competitor_audit", "Full competitor audit: SEO score, CRO checks, recommendations", self._tool_competitor_audit, {"url": "string", "brand_name": "string optional"})
        self.register("competitor_compare", "Side-by-side audit of two URLs", self._tool_competitor_compare, {"url_1": "string", "url_2": "string"})
        # Content (6)
        self.register("generate_copy", "Generate AIDA/PAS/hero copy for a product", self._tool_generate_copy, {"product": "string", "benefits": "string", "audience": "string"})
        self.register("email_sequence", "Generate a 5-email nurture sequence", self._tool_email_sequence, {"product": "string", "benefits": "string", "audience": "string"})
        self.register("social_calendar", "Generate a 30-day social content calendar (JSON)", self._tool_social_calendar, {"product": "string", "industry": "string", "audience": "string"})
        self.register("keyword_brief", "SEO keyword brief from product + benefits", self._tool_keyword_brief, {"product": "string", "industry": "string", "audience": "string", "benefits": "string optional"})
        self.register("brand_strategy", "Generate brand positioning statement", self._tool_brand_strategy, {"product": "string", "industry": "string", "audience": "string"})
        self.register("seo_analyze", "Analyze text for basic SEO score", self._tool_seo_analyze, {"text": "string", "keyword": "string optional"})
        # Visuals (6) — includes new high-end branding + custom size
        self.register("generate_visual", "Generate SVG hero banner + preview (supports custom width/height)", self._tool_generate_visual, {"product": "string", "headline": "string", "primary_color": "string optional", "width": "number optional", "height": "number optional"})
        self.register("landing_page", "Generate a full HTML landing page with brand colors", self._tool_landing_page, {"product": "string", "industry": "string", "audience": "string", "benefits": "string optional"})
        self.register("generate_image", "Generate an image using the configured provider. Public fallback requires explicit consent. Saves the complete image and returns its path.", self._tool_generate_image, {"prompt": "string", "width": "number optional", "height": "number optional"})
        self.register("generate_logo", "Generate high-end logo — lettermark, wordmark, combination, abstract, pictorial, emblem — custom size, brand colors, variants primary/reversed/icon-only", self._tool_generate_logo, {"brand": "string", "style": "string optional", "primary_color": "string optional", "secondary_color": "string optional", "variant": "string optional", "width": "number optional", "height": "number optional"})
        self.register("branding_kit", "Generate full branding kit — primary logo, reversed, icon-only, wordmark, lettermark, abstract, emblem, favicon 512, social avatar 500, color_palette.json, brand_guidelines.md, logo_usage.md — high-end offline", self._tool_branding_kit, {"brand": "string", "primary_color": "string optional", "secondary_color": "string optional", "industry": "string optional", "tagline": "string optional"})
        self.register("generate_custom_visual", "Generate custom size banner/ad — any width/height 50-5000 + presets: medium_rectangle 300x250, leaderboard 728x90, half_page 300x600, mobile_banner 320x50, fb_feed 1200x628, fb_square 1080x1080, fb_story 1080x1920, linkedin_feed 1200x627, youtube_thumbnail 1280x720, etc.", self._tool_generate_custom_visual, {"product": "string", "width": "number", "height": "number", "preset": "string optional", "primary_color": "string optional", "headline": "string optional"})
        # Data (3)
        self.register("roi_calculator", "Calculate 3-year ROI vs a monthly SaaS spend", self._tool_roi_calc, {"monthly_spend": "number", "brandforge_price": "number optional"})
        self.register("list_campaigns", "List all saved campaigns", self._tool_list_campaigns, {})
        self.register("calendar_ics", "Export the 30-day social calendar as an .ics file (Google/Apple/Outlook importable)", self._tool_calendar_ics, {"product": "string", "industry": "string optional"})
        # Memory (2)
        self.register("search_memory", "Search long-term memory", self._tool_search_memory, {"query": "string"})
        self.register("save_memory", "Save a note to long-term memory", self._tool_save_memory, {"key": "string", "value": "string"})

    def register(self, name: str, description: str, func: Callable, params: Dict[str, str]):
        self.tools[name] = {"name": name, "description": description, "function": func, "params": params}

    def get_tool_descriptions(self) -> str:
        lines = []
        for t in self.tools.values():
            params = ", ".join([f"{k}: {v}" for k, v in t["params"].items()])
            lines.append(f"- {t['name']}({params}): {t['description']}")
        return "\n".join(lines)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [{"name": t["name"], "description": t["description"], "params": t["params"]} for t in self.tools.values()]

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if not isinstance(tool_name, str) or len(tool_name) > 40:
            return {"error": "Invalid tool name"}
        safe_name = _safe_slug(tool_name.strip().lower(), 40)
        if safe_name not in self.tools:
            return {"error": f"Tool {safe_name} not found"}
        if not isinstance(args, dict):
            return {"error": "Args must be dict"}
        try:
            if len(json.dumps(args, ensure_ascii=False, allow_nan=False)) > 5000:
                return {"error": "Args too large"}
        except (TypeError, ValueError):
            return {"error": "Args must be JSON-serializable"}
        try:
            return self.tools[safe_name]["function"](**args)
        except TypeError as e:
            return {"error": f"Invalid args for {safe_name}: {str(e)[:100]}"}
        except Exception as e:
            return {"error": f"{safe_name} failed: {str(e)[:150]}"}

    # ---------- research & audit ----------

    def _tool_web_search(self, query: str) -> Dict:
        query = str(query or "").strip()
        if not query or len(query) > 200:
            return {"error": "Invalid query"}
        ws = self._get_searcher()
        results = ws.search(query, max_results=3)
        return {
            "query": query[:100],
            "live": bool(results),
            "results": results,
            "note": None if results else "Live search unavailable (offline/limited network). No results fabricated.",
        }

    def _tool_inspect_url(self, url: str) -> Dict:
        if not url or len(url) > 500:
            return {"error": "Invalid URL"}
        ws = self._get_searcher()
        text = ws.inspect_competitor_url(url[:500])
        return {"url": url[:200], "extracted": text[:3000], "word_count": len(text.split())}

    def _tool_competitor_audit(self, url: str, brand_name: str = "Competitor") -> Dict:
        if not url or len(url) > 500:
            return {"error": "Invalid URL"}
        ws = self._get_searcher()
        return ws.deep_competitor_analysis(url[:500], brand_name[:80])

    def _tool_competitor_compare(self, url_1: str, url_2: str) -> Dict:
        if not url_1 or not url_2 or len(url_1) > 500 or len(url_2) > 500:
            return {"error": "Provide two valid URLs (url_1, url_2)"}
        ws = self._get_searcher()
        a = ws.browser_audit(url_1[:500], take_screenshot=False)
        b = ws.browser_audit(url_2[:500], take_screenshot=False)
        return {
            "a": {"url": url_1[:200], "score": a.get("score"), "recommendations": a.get("recommendations", [])[:5]},
            "b": {"url": url_2[:200], "score": b.get("score"), "recommendations": b.get("recommendations", [])[:5]},
            "verdict": (
                f"{url_1[:60]} leads on measured SEO/CRO signals." if (a.get("score") or 0) > (b.get("score") or 0)
                else f"{url_2[:60]} leads on measured SEO/CRO signals."
            ) if (a.get("score") is not None and b.get("score") is not None) else "Could not audit one or both pages.",
        }

    # ---------- content ----------

    def _tool_generate_copy(self, product: str, benefits: str, audience: str) -> Dict:
        product = _clean_text(product, 80) or "Your product"
        benefits = _clean_text(benefits, 200) or "Details to review"
        audience = _clean_text(audience, 80) or "your audience"
        parts = [b.strip() for b in re.split(r"[,;\n]+", benefits) if b.strip()] or ["Details to review"]
        b1, b2 = parts[0], parts[1] if len(parts) > 1 else parts[0]
        copy_text = f"""**AIDA Ad for {product}:**
Attention: Still comparing {audience} options and second-guessing?
Interest: {product} — {b1}, and {b2}.
Desire: Lead with the benefit you can substantiate. Add your approved proof here.
Action: Invite people to {product}'s approved next step.

**PAS LinkedIn:**
Problem: {audience} options can be difficult to compare.
Agitate: Unclear differences make a considered purchase harder.
Solution: {product} — {b1}, {b2}, explained in the open.

**Email:**
Subject: A clearer look at {product}
Body: Founder — here is a concise look at {product}: {b1} and {b2}. Add the verified detail, price, and next step your audience needs before sending.
"""
        return {"product": product, "copy": copy_text}

    def _tool_email_sequence(self, product: str, benefits: str, audience: str) -> Dict:
        product = _clean_text(product, 80) or "Your product"
        benefits = _clean_text(benefits, 200) or "Details to review"
        audience = _clean_text(audience, 80) or "your audience"
        b = benefits.split(",")[0].strip() or "Details to review"
        seq = [
            {"day": 1, "subject": f"A clearer look at {product}", "body": f"Introduce {product} and the approved benefit: {b}. Add the correct welcome details and reply address before sending."},
            {"day": 3, "subject": f"How to compare {audience} options", "body": f"Explain the decision your audience is making and show how to evaluate {b}. Replace this draft with verified product details."},
            {"day": 7, "subject": "Proof over promises", "body": f"Share a real, permissioned proof point related to {b}. Do not publish a result, statistic, testimonial, or time frame until it is verified."},
            {"day": 14, "subject": f"A practical next step for {product}", "body": f"Give readers one useful action connected to {b}, then add the approved offer, price, and CTA."},
            {"day": 30, "subject": f"Is {product} right for you?", "body": f"Invite an honest fit check. State who {product} is for, who it is not for, and the next step without pressure or unsupported urgency."},
        ]
        return {"product": product, "sequence": seq}

    def _tool_social_calendar(self, product: str, industry: str, audience: str) -> Dict:
        product = _clean_text(product, 80) or "Your product"
        industry = _clean_text(industry, 80) or "your industry"
        audience = _clean_text(audience, 80) or "your audience"
        themes = [
            "Behind-the-scenes", "Customer story (real, specific)", "Myth-busting in {ind}",
            "Quick tip that saves time", "Comparison: us vs the usual way", "FAQ answer from real customers",
            "Milestone / number you can prove", "Founder POV: why we built this",
        ]
        posts = []
        for day in range(1, 31):
            t = themes[(day - 1) % len(themes)]
            posts.append({
                "day": day,
                "theme": t.format(ind=industry),
                "hook": f"{product} — day {day}: {t.split(':')[0] if ':' in t else t.format(ind=industry)}",
                "cta": "Link in comments" if day % 3 == 0 else "DM me 'DETAILS'",
            })
        return {"product": product, "days": len(posts), "posts": posts}

    def _tool_keyword_brief(self, product: str, industry: str, audience: str, benefits: str = "") -> Dict:
        product = _clean_text(product, 80) or "Your product"
        industry = _clean_text(industry, 80) or "your industry"
        audience = _clean_text(audience, 80) or "your audience"
        benefits = [_clean_text(b, 60) for b in re.split(r"[,;]+", str(benefits or "")) if _clean_text(b, 60)][:4]
        kws = [
            {"keyword": f"{product}", "intent": "brand", "usage": "Homepage H1, title tag"},
            {"keyword": f"best {industry} for {audience}", "intent": "commercial", "usage": "Comparison blog post"},
            {"keyword": f"{industry} vs alternatives", "intent": "commercial", "usage": "Comparison page, schema"},
            {"keyword": f"how to choose {industry} service", "intent": "informational", "usage": "Guide blog post, FAQ schema"},
        ]
        for b in benefits[:3]:
            kws.append({"keyword": f"{b} {industry}", "intent": "commercial", "usage": "Feature page / ad copy"})
        return {"product": product, "keywords": kws[:8], "note": "Validate volume in a keyword tool before committing; offline heuristic only."}

    def _tool_brand_strategy(self, product: str, industry: str, audience: str) -> Dict:
        product = _clean_text(product, 80)
        industry = _clean_text(industry, 80)
        audience = _clean_text(audience, 80)
        return {
            "product": product,
            "industry": industry,
            "audience": audience,
            "positioning": f"For {audience} comparing {industry} options, {product} is the option that verifies before it promises.",
            "archetype": "Sage + Creator",
            "tone": "Direct, confident, specific",
            "colors": ["#E8B54A Gold (premium CTA)", "#0F172A Navy (trust)", "#10B981 Emerald (action)"],
        }

    def _tool_seo_analyze(self, text: str, keyword: str = "") -> Dict:
        text = str(text or "")
        keyword = _clean_text(keyword, 100)
        if not text or len(text) > 5000:
            return {"error": "Invalid text"}
        words = len(text.split())
        has_keyword = keyword.lower() in text.lower() if keyword else False
        density = (text.lower().count(keyword.lower()) / max(words, 1) * 100) if keyword else 0
        score = 0
        score += 30 if words >= 300 else (15 if words >= 100 else 0)
        score += 25 if has_keyword else 0
        score += 15 if keyword and 0.3 <= density <= 3.0 else 5
        score += 15 if re.search(r"\n\s*# ", text) or text.count("#") >= 2 else 5
        return {"word_count": words, "has_keyword": has_keyword, "density": round(density, 2),
                "score": min(100, score),
                "recommendations": [
                    ("Add the target keyword naturally" if not has_keyword else "Keyword present"),
                    ("Aim for 300+ words" if words < 300 else "Length OK"),
                    ("Use clear headings" if score < 75 else "Structure OK"),
                ]}

    def _store_generated(self, text, extension='svg'):
        import secrets
        if len(text.encode('utf-8')) > 5_000_000:
            raise ValueError('Generated file exceeds the supported size')
        name = 'tool_' + secrets.token_hex(6) + '.' + extension
        path = os.path.join(self.output_dir, name)
        atomic_write_text(path, text)
        return {'saved_to':path, 'view_url':'/api/files/generated/'+name}

    # ---------- visuals — includes new high-end branding + custom size ----------

    def _tool_generate_visual(self, product: str, headline: str, primary_color: str = "#E8B54A", width: int = 1200, height: int = 630) -> Dict:
        product = _clean_text(product, 80)
        headline = _clean_text(headline, 80)
        try:
            from modules.visual_designer import VisualDesigner
            class _Dummy: pass
            designer = VisualDesigner(_Dummy())
            try:
                w, h = int(width), int(height)
            except (TypeError, ValueError) as exc:
                log.debug("generate_custom_visual: bad size %r/%r (%s) — defaulting to 1200x630", width, height, exc)
                w, h = 1200, 630
            svg = designer.generate_custom_banner_svg(product, headline, w, h, primary_color[:20])
            return {**self._store_generated(svg), "product": product, "svg_length": len(svg), "width": w, "height": h, "svg": svg, "svg_preview": svg[:800]}
        except Exception as e:
            return {"error": str(e)[:100]}

    def _tool_generate_custom_visual(self, product: str, width: int, height: int, preset: str = "", primary_color: str = "#E8B54A", headline: str = "") -> Dict:
        """Generate a custom-dimension banner with user-defined width and height."""
        product = _clean_text(product, 80) or "Your product"
        headline = _clean_text(headline, 80) or f"For {product}"
        try:
            from modules.visual_designer import VisualDesigner, AD_SIZES
            class _Dummy: pass
            designer = VisualDesigner(_Dummy())
            # If preset provided, use preset dimensions
            if preset and preset in AD_SIZES:
                width, height = AD_SIZES[preset][0], AD_SIZES[preset][1]
            try:
                w, h = int(width), int(height)
            except (TypeError, ValueError) as exc:
                log.debug("generate_custom_visual: bad size %r/%r (%s) — defaulting to 300x250", width, height, exc)
                w, h = 300, 250
            w = max(50, min(w, 5000))
            h = max(50, min(h, 5000))
            # Use custom banner generator — supports any size + presets
            svg = designer.generate_custom_banner_svg(product, headline, w, h, primary_color[:20], "#0F172A", product, [], "Get Started", "ad")
            return {
                **self._store_generated(svg),
                "product": product,
                "preset": preset or "custom",
                "width": w,
                "height": h,
                "description": AD_SIZES.get(preset, (w,h,"Custom size"))[2] if preset in AD_SIZES else f"Custom {w}x{h}",
                "svg_length": len(svg),
                "svg": svg,
                "svg_preview": svg[:800],
                "available_presets": list(AD_SIZES.keys()),
            }
        except Exception as e:
            return {"error": str(e)[:150]}

    def _tool_generate_logo(self, brand: str, style: str = "lettermark", primary_color: str = "#E8B54A", secondary_color: str = "#0F172A", variant: str = "primary", width: int = 1024, height: int = 1024) -> Dict:
        """Generate high-end logo — logo banana, high-end, custom size, variants."""
        brand = _clean_text(brand, 40) or "Brand"
        style = _clean_text(style, 20) or "lettermark"
        variant = _clean_text(variant, 20) or "primary"
        try:
            w, h = int(width), int(height)
        except (TypeError, ValueError) as exc:
            log.debug("generate_logo: bad size %r/%r (%s) — defaulting to 1024x1024", width, height, exc)
            w, h = 1024, 1024
        w = max(50, min(w, 5000))
        h = max(50, min(h, 5000))
        try:
            from modules.visual_designer import VisualDesigner
            class _Dummy: pass
            designer = VisualDesigner(_Dummy())
            svg = designer.generate_logo_svg(brand, style, primary_color[:20], secondary_color[:20], variant, w, h)
            # Save to output
            safe_brand = re.sub(r"[^a-zA-Z0-9_-]", "_", brand)[:20]
            name = f"logo_{safe_brand}_{style}_{variant}_{w}x{h}.svg"
            path = os.path.join(self.output_dir, name)
            try:
                atomic_write_text(path, svg)
            except OSError:
                return {"error":"Logo could not be saved. Check the output folder permissions."}
            return {
                "brand": brand,
                "style": style,
                "variant": variant,
                "width": w,
                "height": h,
                "saved_to": path,
                "svg_length": len(svg),
                "svg": svg,
                "svg_preview": svg[:800],
                "note": "High-end SVG logo, offline, no API key, review before publishing. For PNG, convert SVG to PNG 32x32 favicon, 500x500 avatar, etc.",
            }
        except Exception as e:
            return {"error": str(e)[:150]}

    def _tool_branding_kit(self, brand: str, primary_color: str = "#E8B54A", secondary_color: str = "#0F172A", industry: str = "General", tagline: str = "") -> Dict:
        """Generate a full branding kit: 8 logo variants, color palette and
        usage guidelines for the given brand and colors."""
        brand = _clean_text(brand, 40) or "Brand"
        industry = _clean_text(industry, 80) or "General"
        tagline = _clean_text(tagline, 120) or f"{brand} — {industry}"
        try:
            from modules.visual_designer import VisualDesigner
            class _Dummy: pass
            designer = VisualDesigner(_Dummy())
            kit = designer.generate_branding_kit(brand, primary_color[:20], secondary_color[:20], industry, tagline)
            # Save all files to output/branding_{brand}/
            safe_brand = re.sub(r"[^a-zA-Z0-9_-]", "_", brand)[:20]
            kit_dir = os.path.join(self.output_dir, f"branding_{safe_brand}")
            os.makedirs(kit_dir, exist_ok=True)
            saved = []
            for fname, content in kit.items():
                fpath = os.path.join(kit_dir, fname)
                try:
                    # JSON vs text
                    if fname.endswith(".json"):
                        atomic_write_text(fpath, content)
                    else:
                        atomic_write_text(fpath, content)
                    saved.append(fname)
                except Exception:
                    return {"error": "Branding kit could not be completely saved. Check output folder permissions.", "saved_files": saved}
            return {
                "brand": brand,
                "kit_dir": kit_dir,
                "files": saved,
                "count": len(saved),
                "note": "Full high-end branding kit generated offline. Includes primary/reversed/icon-only/wordmark/lettermark/abstract/emblem logos, favicon 512, social avatar 500, color_palette.json, brand_guidelines.md, logo_usage.md. Convert SVG to PNG for favicon 32x32, 16x16, avatar PNG as needed. Review before publishing.",
            }
        except Exception as e:
            return {"error": str(e)[:200]}

    def _tool_landing_page(self, product: str, industry: str, audience: str, benefits: str = "") -> Dict:
        from modules.visual_designer import VisualDesigner
        class _Dummy: pass
        designer = VisualDesigner(_Dummy())
        bens = [b.strip() for b in re.split(r"[,;]+", (benefits or "")) if b.strip()][:6]
        page = designer.generate_landing_page(product[:80], industry[:80], audience[:120], bens)
        return {**self._store_generated(page, "html"), "product": product[:80], "length": len(page), "preview": page[:800], "html": page, "note": "Preview is a source snippet; html contains the complete portable document"}

    # ---------- data ----------

    def _tool_roi_calc(self, monthly_spend: float, brandforge_price: float = 199) -> Dict:
        try:
            monthly_spend = float(monthly_spend)
            brandforge_price = float(brandforge_price)
            if not math.isfinite(monthly_spend) or not math.isfinite(brandforge_price):
                return {"error": "Invalid numbers"}
            if monthly_spend < 0 or monthly_spend > 100000 or brandforge_price < 0 or brandforge_price > 100000:
                return {"error": "Invalid numbers"}
        except (TypeError, ValueError, OverflowError):
            return {"error": "Invalid numbers"}
        three_year = monthly_spend * 36
        saving = three_year - brandforge_price
        roi = (saving / brandforge_price * 100) if brandforge_price else 0
        payback = round((brandforge_price / monthly_spend * 30) if monthly_spend else 0, 1)
        note = None
        if saving <= 0:
            note = (
                f"At ${monthly_spend:,.0f}/mo, a ${brandforge_price:,.0f} one-time tool does "
                f"not pay back within 3 years — your current stack is already cheaper. "
                f"This calculator is honest about it."
            )
        return {
            "monthly": monthly_spend,
            "three_year_saas": round(three_year, 2),
            "brandforge_once": brandforge_price,
            "you_save": round(saving, 2),
            "roi_percent": round(roi, 1),
            "assumptions": "Illustrative cost comparison only: assumes the stated monthly tools are actually replaced, excludes provider fees, hosting, support, tax and time. Not measured business ROI.",
            "payback_days": payback,
            "note": note,
        }

    def _tool_list_campaigns(self) -> List[str]:
        try:
            from modules.project_manager import ProjectManager
            return ProjectManager(base_dir=self.base_dir).list_campaigns()[:20]
        except Exception as e:
            return [f"Error: {str(e)[:100]}"]

    def _tool_generate_image(self, prompt: str, width: int = 1200, height: int = 630) -> Dict:
        prompt = _clean_text(prompt, 200)
        if not prompt:
            return {"error": "Prompt required"}
        try:
            w, h = int(width), int(height)
        except (TypeError, ValueError):
            w, h = 1200, 630
        # An explicit tool call may use the configured image provider; it
        # must not override Off or switch to a public service without consent.
        from modules.ai_image_designer import AIImageDesigner
        engine = AIImageDesigner(base_dir=self.base_dir)
        if engine.provider_setting == 'off':
            return {"image":None,"note":"Image generation is turned off in Settings."}
        shot = engine.generate_design_image(prompt, 'General', 'customers', None, '#E8B54A', '#0F172A', w, h, allow_network=True)
        data = shot.get('bytes') if shot else None
        provider_used = shot.get('provider') if shot else None
        if not data:
            return {"image": None,
                    "note": "Image API unavailable right now — template SVG visuals remain the deliverable (labeled, never faked)."}
        import secrets
        extension = 'png' if data.startswith(b'\x89PNG\r\n\x1a\n') else 'jpg'
        name = f"ai_image_{secrets.token_hex(6)}.{extension}"
        path = os.path.join(self.output_dir, name)
        try:
            if len(data)>5_000_000:
                return {"error":"Image exceeds the supported 5 MB limit; no partial file was saved."}
            data = bytes(data)
            atomic_write_bytes(path, data)
        except (OSError, TypeError) as e:
            return {"error": str(e)[:100]}
        return {
            "provider": provider_used,
            "saved_to": path,
            # Dashboard-viewable URL — without this the chat could only report
            # a PC file path the user had to hunt for in Explorer.
            "view_url": f"/api/files/generated/{name}",
            "bytes": len(data),
            "prompt": prompt,
        }

    def _tool_calendar_ics(self, product: str, industry: str = "") -> Dict:
        from datetime import date, timedelta
        product = _clean_text(product, 80)
        if not product:
            return {"error": "Product required"}
        industry = _clean_text(industry, 80) or "general"
        posts = self._tool_social_calendar(product, industry, "your audience")["posts"]

        def esc(t):
            return str(t).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

        import hashlib
        start = date.today()
        calendar_id = hashlib.sha256(product.encode("utf-8")).hexdigest()[:12]
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
                 "PRODID:-//BrandForge OS//Social Calendar//EN", "CALSCALE:GREGORIAN"]
        for p in posts:
            d = start + timedelta(days=p["day"] - 1)
            lines += ["BEGIN:VEVENT",
                      f"UID:vg-{calendar_id}-{p['day']}@brandforge-os",
                      f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                      f"SUMMARY:{esc(p['theme'])}",
                      f"DESCRIPTION:{esc(p['hook'] + ' | CTA: ' + p['cta'])}",
                      "END:VEVENT"]
        lines.append("END:VCALENDAR")
        folded = []
        for line in lines:
            while len(line.encode("utf-8")) > 75:
                cut = 74
                while len(line[:cut].encode("utf-8")) > 74:
                    cut -= 1
                folded.append(line[:cut])
                line = " " + line[cut:]
            folded.append(line)
        path = os.path.join(self.output_dir, "social_calendar.ics")
        lines = folded
        try:
            atomic_write_text(path, "\r\n".join(lines) + "\r\n")
        except OSError as e:
            return {"error": str(e)[:100]}
        return {"saved_to": path, "events": len(posts),
                "note": "Import into Google Calendar, Apple Calendar or Outlook."}

    # ---------- memory ----------

    def _tool_search_memory(self, query: str) -> List[Dict]:
        if not query or len(query) > 200:
            return []
        try:
            return self._get_memory().search_history(
                query[:100], limit=5, client_id=self._active_client_id()
            )
        except Exception:
            return []

    def _tool_save_memory(self, key: str, value: str) -> Dict:
        if not key or not value or len(key) > 80 or len(value) > 1000:
            return {"error": "Invalid key/value"}
        try:
            if not self._get_memory().save_long_term(key.strip(), value.strip(), client_id=self._active_client_id()):
                return {"error": "Memory note was not saved. Check local storage and try again."}
            return {"saved": True}
        except Exception as e:
            return {"error": str(e)[:100]}
