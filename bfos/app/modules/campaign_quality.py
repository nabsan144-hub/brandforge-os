"""Explainable campaign readiness scoring & readability metrics.

A score is a workflow aid, not a guarantee of legal compliance, performance, or
platform approval. It evaluates deterministic, reviewable signals only.
"""

import re
from typing import Dict, List


def _count_syllables(word: str) -> int:
    w = word.lower().strip(".:;?!,")
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r'(?:[^laeiouy]|ed|es|e)$', '', w)
    w = re.sub(r'^y', '', w)
    syllables = len(re.findall(r'[aeiouy]{1,2}', w))
    return max(1, syllables)


def calculate_readability(text: str) -> Dict[str, object]:
    """Calculate Flesch Reading Ease and text statistics."""
    source = str(text or "").strip()
    words = re.findall(r'\b[A-Za-z0-9\'-]+\b', source)
    sentences = [s for s in re.split(r'[.!?]+', source) if s.strip()]
    
    word_count = len(words)
    sentence_count = max(1, len(sentences))
    if word_count == 0:
        return {
            "word_count": 0,
            "character_count": len(source),
            "reading_ease": None,
            "reading_level": "Not measured (English-only heuristic)",
            "est_read_time_seconds": 0,
        }
    
    total_syllables = sum(_count_syllables(w) for w in words)
    words_per_sentence = word_count / sentence_count
    syllables_per_word = total_syllables / word_count
    
    # Standard Flesch Reading Ease formula
    flesch = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)
    score = max(0, min(100, round(flesch)))
    
    level = "Easy" if score >= 80 else "Conversational" if score >= 60 else "Standard" if score >= 40 else "Complex"
    read_time = round((word_count / 200) * 60) # 200 WPM
    
    return {
        "word_count": word_count,
        "character_count": len(source),
        "reading_ease": score,
        "reading_level": level,
        "est_read_time_seconds": read_time,
    }


def score_campaign(copy_text: str, brand_promise: str, proof_points: str, claim_review: Dict[str, object]) -> Dict[str, object]:
    text = str(copy_text or "")[:15000]
    lower = text.lower()
    claim_review = claim_review if isinstance(claim_review, dict) else {}
    checks: List[Dict[str, object]] = []

    def add(label: str, passed: bool, weight: int, guidance: str) -> None:
        checks.append({"label": label, "passed": passed, "weight": weight, "guidance": guidance})

    add(
        "Clear call to action",
        bool(re.search(r"\b(get started|see details|book|buy|shop|learn more|contact|try|download|sign up|cta)\b", lower)),
        20,
        "Add one specific next step, such as booking, buying, requesting a quote, or learning more.",
    )
    add(
        "Specific benefit included",
        len(text.split()) >= 80,
        15,
        "Add a concrete customer benefit and enough context to explain why it matters.",
    )
    promise_terms = [term for term in re.findall(r"[A-Za-z]{4,}", str(brand_promise or "").lower())]
    add(
        "Brand promise reflected",
        not promise_terms or any(term in lower for term in promise_terms),
        20,
        "Use the approved brand promise in the message when it fits the campaign.",
    )
    proof_terms = [term for term in re.findall(r"[A-Za-z0-9]{4,}", str(proof_points or "").lower())]
    add(
        "Approved proof considered",
        not proof_terms or any(term in lower for term in proof_terms),
        15,
        "Where relevant, add an approved proof point instead of an unsupported claim.",
    )
    try:
        warnings = max(0, int((claim_review or {}).get("warning_count") or 0))
    except (TypeError, ValueError, OverflowError):
        warnings = 0
    add(
        "No Claim Guard warnings",
        warnings == 0,
        30,
        "Review every Claim Guard item, then substantiate, remove, or rewrite the risky wording.",
    )

    from modules.draft_integrity import sections
    complete = len(sections(text)) == 5
    add("All requested copy sections present", complete, 0,
        "Include AIDA, PAS, welcome email, hero headline and CTA before reviewing the campaign as a complete pack.")
    score = sum(item["weight"] for item in checks if item["passed"])
    if not complete: score = min(score, 59)
    failed = [item["guidance"] for item in checks if not item["passed"]]
    status = "ready_for_internal_review" if score >= 80 and warnings == 0 and complete else "needs_revision"
    
    readability = calculate_readability(text)
    
    return {
        "score": score,
        "status": status,
        "checks": checks,
        "next_steps": failed[:4],
        "readability": readability,
        "disclaimer": "Workflow score only. Verify factual claims, legal requirements, platform policies, and final client approval before publishing.",
    }
