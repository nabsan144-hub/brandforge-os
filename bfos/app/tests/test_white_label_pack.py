from modules.campaign_pack import build_campaign_pack


def test_white_label_pack_uses_agency_footer_and_can_hide_brandforge_branding():
    pack = build_campaign_pack(
        {
            "product_name": "Apex Coffee", "industry": "Retail", "target_audience": "Remote workers",
            "strategy_text": "A clear strategy.", "agency_brand": "Apex Growth Studio",
            "agency_footer": "Prepared by Apex Growth Studio · hello@example.test",
            "show_brandforge_branding": False,
        },
        {"copy_text": "Book today for transparent pricing.", "key_benefits": "Transparent pricing"},
        {"quality_score": {"score": 80, "status": "ready_for_internal_review", "next_steps": []}, "claim_review": {"warnings": []}},
        "apex",
    )
    approval = pack["01_strategy_and_approval.html"]
    assert "Apex Growth Studio" in approval
    assert "hello@example.test" in approval
    assert "Prepared with BrandForge OS" not in approval
