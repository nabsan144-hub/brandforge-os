"""Agent discussion (council) mode for the dashboard chat.

The campaign swarm is a pipeline (agents pass work down the chain). This
module is different: three personas literally read each other's answers and
respond to them in turns, so the user SEES the agents discussing — the
strategist plans, the copywriter pushes back with what will actually sell,
the critic attacks both, and a final combined plan closes the round.

Sweep 19: the council now (a) streams its turns so the customer watches the
debate happen instead of staring at dots, and (b) grounds itself in real
facts — the active brand's profile plus a live inspection of any URL the
customer pastes — so answers are about THEIR business, not strategy-speak.

Honesty rules (same as the rest of the product):
- Every turn goes through the real engine — online providers get model-grade
  answers, offline gets template-grade answers, and nothing pretends otherwise.
- If one agent call fails, the transcript keeps going and says which agent
  dropped out; no fabricated turn.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Any, Iterator, List, Optional, TYPE_CHECKING

from modules.security import safe_text as _safe_text

if TYPE_CHECKING:
    from engines.ai_engine import AIEngine

log = logging.getLogger(__name__)

# Bounded on purpose: 3 discussion turns + 1 verdict. Each turn is a real
# provider call, so an unbounded debate would burn quota silently.
MAX_TOKENS_TURN = 550

_URL_RE = re.compile(r"https?://[^\s)>\]]+")

AGENTS = [
    {
        "id": "strategist",
        "label": "Brand Strategist",
        "icon": "🧭",
        "system": (
            "You are the Brand Strategist in a 3-agent council (Strategist, "
            "Copywriter, Critic). Short, decisive, specific. 4-8 lines max."
        ),
        "task": (
            "Open the discussion: name the positioning angle, the ONE audience "
            "to hit first, and the single strongest proof point. No fluff."
        ),
    },
    {
        "id": "copywriter",
        "label": "Direct-Response Copywriter",
        "icon": "✍️",
        "system": (
            "You are the Direct-Response Copywriter in a 3-agent council. You "
            "respect the strategist but argue from what actually sells. "
            "4-8 lines max."
        ),
        "task": (
            "Respond to the strategist: keep what works, challenge what won't "
            "convert, and give the hook line + CTA you'd actually ship."
        ),
    },
    {
        "id": "critic",
        "label": "Quality Critic",
        "icon": "🔍",
        "system": (
            "You are the Quality Critic in a 3-agent council. Brutally honest, "
            "no sugarcoating, but constructive. 4-8 lines max."
        ),
        "task": (
            "Attack both previous answers: name the weakest claim, the fluff, "
            "and any risk of an unverifiable promise. Then say what MUST change."
        ),
    },
]


def _gather_facts(ai: "AIEngine", message: str, context: Optional[Dict[str, str]]) -> str:
    """Ground the debate in reality: active brand profile + a live read of any
    URL the customer referenced. Without this the council produced generic
    strategy-speak that founders found 'samjh se bahar'."""
    parts: List[str] = []
    context = context or {}
    if context.get("brand"):
        parts.append(f"Active brand: {context['brand']}")
    if context.get("industry"):
        parts.append(f"Industry: {context['industry']}")
    if context.get("target_audience"):
        parts.append(f"Target audience: {context['target_audience']}")

    m = _URL_RE.search(message or "")
    if m:
        url = m.group(0)[:500]
        parts.append(f"The customer referenced this live URL: {url}")
        tools = getattr(ai, "tools", None)
        if tools is not None:
            try:
                info = tools.execute_tool("inspect_url", {"url": url})
                extracted = (info or {}).get("extracted") or ""
                if extracted:
                    parts.append(
                        f"WHAT THAT SITE ACTUALLY SAYS (extracted live): "
                        f"{extracted[:1400]}"
                    )
            except Exception as e:  # grounding is best-effort, never fatal
                log.warning("council url inspect failed: %s", e)
    return "\n".join(parts)


def stream_council(ai: "AIEngine", message: str,
                   context: Optional[Dict[str, str]] = None,
                   client_id: str = "default") -> Iterator[Dict[str, Any]]:
    """Yield the discussion as it happens: thinking → turn → … → final."""
    message = _safe_text(message, 2000)
    facts = _gather_facts(ai, message, context)
    grounding = (
        f"\n[GROUNDING FACTS — base every claim on these]\n{facts}\n"
        "Rules: quote concrete details from the facts above (real site text, "
        "real brand, real audience). Name actual headline/CTA/color choices. "
        "Never answer with vague strategy-speak; if a fact is missing, say so."
        if facts else ""
    )

    transcript_parts: List[str] = []
    for agent in AGENTS:
        yield {"type": "thinking", "label": agent["label"], "icon": agent["icon"]}
        prior = "\n\n".join(transcript_parts) if transcript_parts else "(you are first)"
        prompt = (
            f"Council question from the founder:\n{message}\n\n"
            f"Earlier turns in this discussion:\n{prior[:2400]}\n"
            f"{grounding}\n"
            f"Your job now: {agent['task']}"
        )
        try:
            reply = ai.generate_text(
                prompt,
                system_prompt=agent["system"],
                max_tokens=MAX_TOKENS_TURN,
                use_tools=False,
                context=context,
                client_id=client_id,
            )
            reply = _safe_text(reply or "", 3000).strip()
        except Exception as e:  # keep the round honest, keep it going
            log.warning("council agent %s failed: %s", agent["id"], e)
            reply = ""
        if not reply:
            reply = "(this agent's call failed — its turn is skipped, nothing was invented)"
        transcript_parts.append(f"{agent['label']}: {reply}")
        yield {"type": "turn", "agent": agent["id"], "label": agent["label"],
               "icon": agent["icon"], "text": reply}

    yield {"type": "thinking", "label": "Council Chair", "icon": "✅"}
    final = ""
    try:
        final = ai.generate_text(
            f"Council question:\n{message}\n\nFull discussion:\n"
            + "\n\n".join(transcript_parts)[:6000]
            + grounding
            + "\n\nDeliver the FINAL combined plan the council agrees on: "
              "positioning, hook, CTA, and the 3 next actions. Short, concrete, "
              "tied to the grounding facts.",
            system_prompt="You are the council chair. Merge the three opinions into one decisive plan.",
            max_tokens=700,
            use_tools=False,
            context=context,
            client_id=client_id,
        )
        final = _safe_text(final or "", 3000).strip()
    except Exception as e:
        log.warning("council final synthesis failed: %s", e)

    yield {
        "type": "final",
        "final": final or "(final synthesis failed — the three agent turns above stand on their own)",
        "provider": getattr(ai, "last_provider", getattr(ai, "provider", "offline")),
    }


def run_council(ai: "AIEngine", message: str,
                context: Optional[Dict[str, str]] = None,
                client_id: str = "default") -> Dict[str, Any]:
    """Non-streaming convenience (kept for the batch endpoint + tests)."""
    turns: List[Dict[str, Any]] = []
    final = ""
    provider = ""
    for ev in stream_council(ai, message, context, client_id):
        if ev["type"] == "turn":
            turns.append(ev)
        elif ev["type"] == "final":
            final = ev["final"]
            provider = ev.get("provider", "")
    return {"turns": turns, "final": final, "provider": provider}
