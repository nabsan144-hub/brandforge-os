

def test_campaign_writes_about_user_product():
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    out = eng.generate_text(
        "Campaign — Product: Apex Coffee, Industry: Retail, Audience: Busy pros, Benefits: organic, fast delivery",
        context={"product": "Apex Coffee", "industry": "Retail", "target_audience": "Busy pros",
                 "key_benefits": "organic, fast delivery"},
    )
    assert "Apex Coffee" in out
    assert "organic" in out
    # The v1.0 bug: BrandForge's own sales copy leaking into customer campaigns
    assert "is the offline OS that delivers" not in out
    assert "BrandForge OS is" not in out.replace("BrandForge — Offline Mode", "")


def test_brand_strategy_about_user_brand():
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    out = eng.generate_text(
        "Brand strategy for GreenMart",
        context={"product": "GreenMart", "industry": "Grocery", "target_audience": "Families"},
    )
    assert "GreenMart" in out
    assert "is the offline OS" not in out


def test_roi_math_in_chat():
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    out = eng.generate_text("ROI: I pay $150/month for tools")
    assert "$5,400" in out or "5400" in out


def test_empty_prompt():
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    out = eng.generate_text("   ")
    assert "No command" in out


def test_extract_context():
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    ctx = eng._extract_context("Product: Apex Coffee\nIndustry: Retail\nAudience: Pros\nBenefits: fast")
    assert ctx["product"] == "Apex Coffee"
    assert ctx["industry"] == "Retail"
    assert ctx["target_audience"] == "Pros"
    assert "fast" in ctx["key_benefits"]


def test_seo_agent_prompt_routes_to_seo_branch():
    """Regression: SEO analyst prompt embeds copy (AIDA...) — must not route to campaign branch."""
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    out = eng.generate_text(
        "SEO & CRO analysis for Apex Coffee.\nCopy:\nAIDA ad — Stop guessing. Apex Coffee gives you organic beans...\n"
        "Give: 1. SEO score /100 2. 5 keyword ideas 3. CRO improvements 4. 3-year ROI vs $200/mo SaaS",
        context={"product": "Apex Coffee", "industry": "Retail", "target_audience": "Busy pros",
                 "key_benefits": "organic, fast delivery"},
    )
    assert "SEO & CRO Suggestions" in out
    assert "Not measured" in out and "78/100" not in out
    assert "Campaign Draft" not in out


def test_quality_sentinel_returns_tightened_draft_not_new_campaign():
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    draft = "AIDA: Stop guessing! Apex Coffee — organic beans, fast delivery.\n\nPAS: Problem: bad coffee. Agitate: you keep buying it."
    out = eng.generate_text(
        f"Quality Sentinel pass — tighten this copy\nScore: hook strength, fluff removal.\nDRAFT:\n{draft}",
        context={"product": "Apex Coffee", "industry": "Retail", "target_audience": "Busy pros",
                 "key_benefits": "organic, fast delivery"},
    )
    assert "Formatting pass" in out
    assert "Stop guessing" in out  # draft content preserved
    assert "Campaign Draft" not in out


def test_brand_strategy_prompt_not_spoofed_by_embedded_copy():
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    out = eng.generate_text(
        "Chief Brand Strategist engagement.\nProduct: GreenMart\nIndustry: Grocery\nTarget: Families\n"
        "Benefits: local produce, weekly boxes\n\nDeliver: 1. Positioning 2. Archetype 3. Pain points 4. Color direction.",
        context={"product": "GreenMart", "industry": "Grocery", "target_audience": "Families",
                 "key_benefits": "local produce, weekly boxes"},
    )
    assert "Brand Strategy" in out
    assert "GreenMart" in out
