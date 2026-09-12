from modules.campaign_quality import score_campaign


def test_quality_score_is_explainable_and_ready_when_checks_pass():
    copy = (
        "Established in 2020, Apex Coffee gives remote workers transparent pricing and reliable delivery. "
        "Enjoy a clear choice without invented claims, then book your first order today. "
        "The campaign explains the practical service, the customer value, the transparent price, "
        "and the next step in straightforward language for a busy customer. "
    ) * 2
    copy += "\nAIDA\nPAS\nWelcome Email\nHero Headline\nCTA: Learn more"
    score = score_campaign(
        copy,
        "Clear choice without invented claims",
        "Established in 2020; transparent pricing",
        {"warning_count": 0},
    )
    assert score["score"] == 100
    assert score["status"] == "ready_for_internal_review"
    assert all(item["passed"] for item in score["checks"])


def test_quality_score_requires_revision_when_claims_are_flagged():
    score = score_campaign("A short message", "", "", {"warning_count": 1})
    assert score["status"] == "needs_revision"
    assert score["score"] < 80
    assert score["next_steps"]
