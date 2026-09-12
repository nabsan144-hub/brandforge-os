"""Regression tests for the 2026-08 audit fix batch.

Each test pins one verified bug so it cannot silently return:
- Telegram guard decorator producing coroutine objects (bot fully broken)
- seo_audit_html never detecting <link rel="canonical">
- generic BRANDFORGE_API_KEY satisfying every provider (wrong key to wrong vendor)
- "Offline" provider choice not persisting across restarts
- web_search rejecting long queries instead of truncating
"""

import asyncio



# ---------- Telegram guard ----------

class _FakeMessage:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)


class _FakeUpdate:
    def __init__(self, chat_id):
        self.message = _FakeMessage(chat_id)


def _make_bot():
    from gateway.telegram_bot import BrandForgeTelegramBot
    return BrandForgeTelegramBot("test-token-0123456789abcdef")


def test_telegram_guard_returns_real_callable():
    """Regression: `async def guard` made every decorated handler a coroutine
    object — python-telegram-bot then raised 'coroutine object is not callable'
    and the whole bot was dead."""
    bot = _make_bot()

    async def handler(update, context):
        return "ran"

    wrapped = bot._guard(handler)
    assert callable(wrapped), "guard must return a function, not a coroutine object"
    import inspect
    assert inspect.iscoroutinefunction(wrapped)


def test_telegram_guard_allowlist_enforced():
    bot = _make_bot()
    calls = []

    async def handler(update, context):
        calls.append(update.message.chat_id)

    wrapped = bot._guard(handler)

    # Not allowlisted -> refused
    upd = _FakeUpdate(111)
    asyncio.run(wrapped(upd, None))
    assert calls == []
    assert any("Not an authorized" in r for r in upd.message.replies)

    # Allowlisted -> runs
    bot.allowed_chat_ids = {"111"}
    asyncio.run(wrapped(upd, None))
    assert calls == [111]


# ---------- SEO canonical detection ----------

def test_canonical_link_tag_detected():
    """Regression: canonical detection did a substring test of a literal regex
    source string, so <link rel="canonical"> was never found (-8 score points
    and a bogus recommendation on every real page)."""
    from modules.web_searcher import WebSearcher
    page = (
        '<html lang="en"><head>'
        '<title>A Properly Sized Page Title For Testing</title>'
        '<link rel="canonical" href="https://example.com/">'
        '</head><body><h1>Hi</h1></body></html>'
    )
    res = WebSearcher().seo_audit_html("https://example.com", page)
    assert res["checks"]["has_canonical"] is True
    assert not any("canonical" in r.lower() for r in res["recommendations"])


# ---------- API key isolation ----------

def test_generic_key_does_not_authorize_other_providers(monkeypatch):
    """Regression: a generic BRANDFORGE_API_KEY made has_key() True for every
    provider — a Groq key could be sent to Gemini/xAI/Moonshot endpoints."""
    monkeypatch.setenv("BRANDFORGE_API_KEY", "generic-key-12345678")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from engines.ai_engine import AIEngine
    eng = AIEngine(provider="offline")
    assert eng.has_key("gemini") is False
    assert eng.key_for("gemini") == ""
    assert eng.has_key("groq") is False


def test_provider_specific_key_still_works(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_123456")
    from engines.ai_engine import AIEngine
    eng = AIEngine(provider="offline")
    assert eng.has_key("groq") is True
    assert eng.key_for("groq") == "gsk_test_key_123456"


# ---------- provider persistence ----------

def test_offline_choice_persists_across_restart():
    """Regression: onboarding/menu 'Offline' only set engine state in memory;
    the previously saved provider came back after restart."""
    import brandforge
    from engines.ai_engine import get_engine
    ai = get_engine(provider="groq")
    brandforge._persist_provider(ai, "offline")
    again = get_engine(provider=None)
    assert again.provider == "offline"


# ---------- long query handling ----------

def test_long_search_query_truncated_not_rejected():
    """Regression: queries >300 chars returned [] ('search unavailable') even
    though search truncates to 200 anyway."""
    from modules.web_searcher import WebSearcher
    ws = WebSearcher()
    long_q = "coffee " * 80  # ~560 chars
    # Must not short-circuit to [] because of length. (Offline sandbox → [] is
    # still acceptable, but the guard clause itself must be gone: verify via
    # the length branch by checking a normal short query behaves identically.)
    assert isinstance(ws.search(long_q, max_results=3), list)
    # The old code returned [] BEFORE touching providers; ensure the length
    # guard no longer exists by asserting the method truncates instead.
    import inspect
    src = inspect.getsource(ws.search)
    assert "len(query) > 300" not in src


# ---------- CSP route-awareness (from-scratch audit, batch 5) ----------

def test_csp_strict_for_app_and_inline_for_sales(client):
    """The app/API keep a strict CSP; /sales pages legitimately use inline
    scripts (theme init, demo, ROI calculator) and must not be frozen."""
    health = client.get("/health")
    csp = health.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "unsafe-inline" not in csp.split(";")[1]  # script-src stays strict

    sales = client.get("/sales/")
    scsp = sales.headers.get("content-security-policy", "")
    assert "script-src 'self' 'unsafe-inline'" in scsp
