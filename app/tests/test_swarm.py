

def test_swarm_produces_full_campaign(tmp_path, engine):
    from modules.swarm_director import SwarmDirector
    from modules.project_manager import ProjectManager

    pm = ProjectManager(base_dir=str(tmp_path))
    swarm = SwarmDirector(engine)
    res = swarm.execute_swarm_campaign("Apex Coffee", "Retail", "Busy professionals",
                                       "organic beans, same-day delivery", client_id="client_x", generate_new_logo=True)

    assert res["strategy_data"]["product_name"] == "Apex Coffee"
    assert "Apex Coffee" in res["strategy_data"]["strategy_text"]
    assert "is the offline OS that delivers" not in res["strategy_data"]["strategy_text"]
    assert res["meta"]["client_id"] == "client_x"
    assert res["meta"]["research_live"] is False
    assert "unavailable" in res["strategy_data"]["market_research"].lower()

    for f in ["hero_banner.svg", "instagram_square.svg", "ad_card.html", "landing_page.html"]:
        assert f in res["visual_files"], f

    # NEW: branding kit included
    assert res["meta"]["branding_kit"] is True
    assert any("branding/" in k for k in res["visual_files"].keys()), "branding kit files should be in visual_files"
    assert "branding/primary_logo.svg" in res["visual_files"]
    assert "branding/color_palette.json" in res["visual_files"]

    pm.save_campaign("apex test", res["strategy_data"], res["copy_data"], res["visual_files"], client_id="client_x")
    saved = pm.get_campaign("apex test")
    assert saved["strategy"]["product_name"] == "Apex Coffee"
    assert saved["client_id"] == "client_x"
    names = [f["name"] for f in saved["files"]]
    assert "hero_banner.svg" in names
    assert "campaign_report.md" in names
    # branding kit files saved
    assert any("primary_logo.svg" in n for n in names)

    zip_path = pm.export_zip("apex test")
    import zipfile
    assert zipfile.is_zipfile(zip_path)
    assert "hero_banner.svg" in zipfile.ZipFile(zip_path).namelist()


def test_swarm_splits_benefits():
    from modules.swarm_director import SwarmDirector
    bens = SwarmDirector._split_benefits("organic, fast, local, fresh, organic, x" * 5)
    assert len(bens) <= 4
    assert "organic" in bens


def test_offline_agents_route_to_their_own_outputs(engine):
    from modules.swarm_director import SwarmDirector
    res = SwarmDirector(engine).execute_swarm_campaign(
        "Apex Coffee", "Retail", "Busy pros", "organic, fast delivery")
    copy = res["copy_data"]["copy_text"]
    strategy = res["strategy_data"]["strategy_text"]
    assert "AIDA" in copy
    assert "PAS" in copy
    assert "Welcome Email" in copy
    assert "Brand Strategy" in strategy
    assert "Archetype" not in copy
    assert "SEO" in res["analysis_data"]["seo_analysis"] or "SEO Score" in res["analysis_data"]["seo_analysis"]


def test_white_label_badge_follows_active_client(engine, tmp_path):
    from modules.client_manager import ClientManager
    from modules.swarm_director import SwarmDirector
    cm = ClientManager(base_dir=str(tmp_path))
    cm.save_client({"client_id": "acme", "client_name": "Acme Bakery",
                    "agency_brand": "ACME BAKERY CO", "industry": "Food",
                    "tone_of_voice": "Warm", "primary_color": "#B45309",
                    "secondary_color": "#1C1917"})
    cm.set_active_client("acme")
    engine.clients = cm
    res = SwarmDirector(engine).execute_swarm_campaign(
        "Sourdough Loaf", "Bakery", "Health bakers", "natural, slow-fermented")
    assert "ACME BAKERY CO" in res["visual_files"]["hero_banner.svg"]
    assert "ACME BAKERY CO" in res["visual_files"]["instagram_square.svg"]
    assert "#B45309" in res["visual_files"]["hero_banner.svg"]


def test_custom_sizes():
    from modules.swarm_director import SwarmDirector
    from engines.ai_engine import get_engine
    import tempfile
    tmp = tempfile.mkdtemp()
    eng = get_engine(provider="offline", data_dir=tmp)
    swarm = SwarmDirector(eng)
    res = swarm.execute_swarm_campaign(
        "Apex Coffee", "Retail", "Busy pros", "organic, fast",
        custom_sizes=[{"width": 300, "height": 250, "preset": "medium_rectangle"}, {"width": 728, "height": 90}]
    )
    assert res["meta"]["custom_sizes"] == 2
    assert "banner_medium_rectangle.svg" in res["visual_files"] or any("300x250" in k or "medium_rectangle" in k for k in res["visual_files"].keys())
    assert "banner_728x90.svg" in res["visual_files"] or any("728x90" in k for k in res["visual_files"].keys())
