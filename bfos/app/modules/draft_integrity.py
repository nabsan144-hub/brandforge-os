"""Structural checks for the editorial pass, not a semantic quality guarantee."""
import re

MARKERS = {
    'aida': r'\bAIDA\b',
    'pas': r'\bPAS\b',
    'email': r'welcome\s+email|email\s+de\s+(?:bienvenida|boas-vindas)|خوش\s*آمدید\s*ای\s*میل|स्वागत\s*ईमेल',
    'hero': r'hero\s+headline|landing\s+hero|titular\s+principal|título\s+principal|مرکزی\s*سرخی|मुख्य\s*शीर्षक',
    'cta': r'\bCTA\b|call\s+to\s+action',
}


def sections(text):
    return {key for key, pattern in MARKERS.items() if re.search(pattern, str(text or ''), re.I)}


def preserves_draft(draft, candidate):
    original, refined = str(draft or ''), str(candidate or '')
    if not refined.strip() or len(refined) < len(original) * .55:
        return False
    if not sections(original).issubset(sections(refined)):
        return False
    # An editor must not quietly lose supplied prices, dates or destinations.
    anchors = re.findall(r'https?://[^\s<>]+|\b\d+(?:[.,]\d+)?\b', original)
    return all(anchor in refined for anchor in anchors)
