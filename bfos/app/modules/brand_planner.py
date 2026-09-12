"""
BRANDFORGE OS - Brand Planner | Production-Ready
"""

from typing import Dict, Any, TYPE_CHECKING

from modules.security import safe_hex

if TYPE_CHECKING:
    from engines.ai_engine import AIEngine


class BrandPlanner:
    def __init__(self, ai_engine: "AIEngine"):
        self.ai = ai_engine

    def generate_brand_strategy(self, product_name: str, industry: str, target_audience: str) -> Dict[str, Any]:
        # Sanitize as DATA only. HTML-escaping belongs at render boundaries
        # (SVG/HTML generators) — escaping here corrupts "Marketing & SaaS".
        import re as _re
        def _clean(s, n=80):
            s = _re.sub(r"<[^>]*>", "", str(s or ""))[:n].strip()
            return s
        product_name = _clean(product_name, 80) or "Brand"
        industry = _clean(industry, 80) or "General"
        target_audience = _clean(target_audience, 80) or "Founders"

        prompt = f"""Create Brand Strategy for:
Product: {product_name}
Industry: {industry}
Audience: {target_audience}

Include:
1. Positioning Statement (1 sentence)
2. Archetype & Tone
3. 3 Personas with pain points
4. Color Palette with psychology"""

        try:
            strategy_text = self.ai.generate_text(prompt, system_prompt="You are world-class CMO, ex-Apple. Be specific, bold, no fluff.", max_tokens=800)
        except Exception:
            strategy_text = (
                f"Positioning: For {target_audience} who need clarity, {product_name} "
                f"is the {industry} option that verifies before it promises."
            )

        primary = "#E8B54A"
        secondary = "#0F172A"
        try:
            if getattr(self.ai, "clients", None):
                active = self.ai.clients.get_active_client()
                primary = safe_hex(active.get("primary_color", primary), primary)
                secondary = safe_hex(active.get("secondary_color", secondary), secondary)
        except Exception:
            pass

        color_palette = [
            {"name": "Primary Gold", "hex": primary, "role": "Premium CTA"},
            {"name": "Secondary Navy", "hex": secondary, "role": "Trust"},
            {"name": "Emerald", "hex": "#10B981", "role": "Action"},
            {"name": "Slate", "hex": "#0F172A", "role": "Background"},
            {"name": "Light", "hex": "#F8FAFC", "role": "Text"},
        ]

        return {
            "product_name": product_name,
            "industry": industry,
            "target_audience": target_audience,
            "strategy_text": strategy_text,
            "color_palette": color_palette,
        }
