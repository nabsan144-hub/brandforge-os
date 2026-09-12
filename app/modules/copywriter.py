"""
BRANDFORGE OS - Copywriter | Production-Ready
"""

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from engines.ai_engine import AIEngine


class Copywriter:
    def __init__(self, ai_engine: "AIEngine"):
        self.ai = ai_engine

    def generate_campaign_copy(self, product_name: str, key_benefits: str, target_audience: str) -> Dict[str, Any]:
        # Sanitize as DATA only — entity-escape at render time, not storage.
        import re as _re
        def _clean(s, n=80):
            return _re.sub(r"<[^>]*>", "", str(s or ""))[:n].strip()
        product_name = _clean(product_name, 80) or "Brand"
        key_benefits = _clean(key_benefits, 200) or ""
        target_audience = _clean(target_audience, 80) or "Founders"

        prompt = f"""Write high-converting copy for:
Product: {product_name}
Benefits: {key_benefits}
Audience: {target_audience}

Include:
1. AIDA Facebook/Instagram Ad with bold hook
2. PAS LinkedIn Post with hashtags
3. Welcome Email Subject, Preheader, Body (150 words)
4. Landing Hero Hook + Subheadline + CTA"""

        try:
            copy_text = self.ai.generate_text(prompt, system_prompt="You are an elite direct-response copywriter. Write specific, honest, high-converting ads — no fake claims.", max_tokens=1000)
        except Exception:
            copy_text = (
                f"AIDA: Lead with the approved benefit. {product_name} — {key_benefits}. "
                f"PAS: Explain the verified customer problem and the cost of inaction without inventing numbers. "
                f"Email: A clear introduction to {product_name}."
            )

        return {
            "product_name": product_name,
            "key_benefits": key_benefits,
            "target_audience": target_audience,
            "copy_text": copy_text,
        }
