"""Deterministic first-pass marketing claim review.

This guard does not make legal decisions or validate claims. It highlights text
for a human reviewer, especially when a client supplied prohibited phrases,
FTC truth-in-advertising guidelines, Amazon title/claim rules, and Meta ad standards.
"""

import re
from typing import Dict, List


_RISK_PATTERNS = {
    "guaranteed outcome": r"\b(?:100%\s*)?guarantee(?:d|s)?\b|\brisk[- ]free\b",
    "absolute best claim": r"\b(?:the )?(?:best|number\s*1|#1|top[- ]rated|bestseller|best[- ]selling)\b",
    "unqualified superlative": r"\b(?:perfect|miracle|revolutionary|unmatched|magic)\b",
    "unqualified urgency": r"\b(?:act now|last chance|only today|limited time offer)\b",
    "disease or health claim": r"\b(?:cure[s]?|heal[s]?|treat[s]?|prevent disease|diagnose|miracle remedy)\b",
    "unsubstantiated pricing claim": r"\b(?:lowest price guaranteed|factory direct|cheapest on earth)\b",
}


def _phrases(value: str, limit: int = 20) -> List[str]:
    candidates = re.split(r"[,;\n|]+", str(value or ""))
    result = []
    for item in candidates:
        phrase = item.strip()[:80]
        if phrase and phrase.lower() not in {x.lower() for x in result}:
            result.append(phrase)
        if len(result) >= limit:
            break
    return result


def review_marketing_copy(text: str, prohibited_claims: str = "") -> Dict[str, object]:
    """Return explainable warnings; never silently alter customer content."""
    source = str(text or "")[:15000]
    warnings: List[Dict[str, str]] = []
    lowered = source.lower()

    for phrase in _phrases(prohibited_claims):
        if phrase.lower() in lowered:
            warnings.append({
                "type": "client_prohibited_phrase",
                "phrase": phrase,
                "message": f"Client rule matched: review or remove “{phrase}”.",
            })

    for label, pattern in _RISK_PATTERNS.items():
        match = re.search(pattern, source, flags=re.IGNORECASE)
        if match:
            warnings.append({
                "type": "general_marketing_risk",
                "phrase": match.group(0),
                "message": f"Potential {label}: substantiate it or rewrite it more precisely according to FTC/platform rules.",
            })

    return {
        "status": "review_needed" if warnings else "clear",
        "warning_count": len(warnings),
        "warnings": warnings,
        "disclaimer": "Automated first pass only; a human must verify legal, platform, and factual compliance before publishing.",
    }
