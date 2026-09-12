"""Fresh-audit regression (1.2.19→1.2.20): free-form chat briefs must
actually reach the offline templates. The dashboard's example chips
("Campaign — Product: X, …", "AIDA ad for my coffee shop") previously
produced copy about "Your product" — the extractor existed but was never
applied on the chat path, and the chat route's client-default context
masked it."""

import tempfile


def _engine(tmp=None):
    from engines.ai_engine import AIEngine
    return AIEngine(provider="offline", data_dir=tmp or tempfile.mkdtemp(prefix="vg_ctx_"))


def test_extract_context_key_value_with_chained_keys():
    e = _engine()
    ctx = e._extract_context(
        "Campaign — Product: Apex Coffee, Industry: Retail, Audience: Busy pros, Benefits: organic, fast delivery")
    assert ctx["product"] == "Apex Coffee"          # not the whole line
    assert ctx["industry"] == "Retail"
    assert ctx["target_audience"] == "Busy pros"
    assert ctx["key_benefits"] == "organic, fast delivery"


def test_extract_context_prose_fallback():
    e = _engine()
    assert e._extract_context("AIDA ad for my coffee shop — organic, family-owned")["product"] == "coffee shop"
    assert e._extract_context("30-day social calendar for my retail brand")["product"] == "retail brand"
    # no phrase to salvage → nothing invented
    assert "product" not in e._extract_context("hello there")


def test_chat_prompt_brief_reaches_template():
    e = _engine()
    out = e.generate_text("Campaign — Product: Apex Coffee, Industry: Retail, "
                          "Audience: Busy pros, Benefits: organic, fast delivery")
    assert "Apex Coffee" in out and "Your product" not in out
    assert "Busy pros" in out


def test_prompt_brief_overrides_client_default_context():
    e = _engine()
    out = e.generate_text(
        "Write copy", context={"industry": "Client Default Industry", "product": "",
                               "target_audience": "Client Audience"},
    ) if False else e.generate_text(
        # route-style context (client defaults) + explicit brief in prompt:
        "Campaign — Product: Apex Coffee, Industry: Retail",
        context={"industry": "Client Default Industry", "target_audience": "Client Audience"})
    assert "Apex Coffee" in out
    assert "Retail" in out
    assert "Client Default Industry" not in out   # explicit prompt value wins
    assert "Client Audience" in out                # unstated key falls back


def test_audit_header_no_placeholder_brand():
    e = _engine()
    out = e.generate_text("Audit https://example.com — give SEO score")
    assert "Website Audit (offline mode)" in out and "Your product" not in out
