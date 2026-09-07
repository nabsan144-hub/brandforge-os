"""Phase 5: desktop engine i18n — 5 locales (en/hi/ur/es/pt).

en stays byte-frozen by tests/test_golden.py; these tests lock the other
four locales and the lang plumbing through API + engine.
"""
import tempfile

from modules.i18n import BUNDLES, LANGS, pick_lang, t

CTX = {
    "product": "Chai House", "industry": "Cafe",
    "target_audience": "students", "key_benefits": "fresh, fast",
}


def _engine():
    from engines.ai_engine import AIEngine
    return AIEngine(provider="offline", data_dir=tempfile.mkdtemp())


def test_pick_lang_subset_aware():
    assert pick_lang(None) == "en"
    assert pick_lang("") == "en"
    assert pick_lang("xx") == "en"
    assert pick_lang("UR") == "ur"
    assert pick_lang(" ur ") == "ur"
    assert pick_lang("pt-BR") == "en"  # not in subset -> en, no crash


def test_every_bundle_covers_every_key():
    for code in LANGS:
        missing = [k for k in BUNDLES["en"] if k not in BUNDLES[code]]
        assert not missing, f"bundle {code} missing keys: {missing}"


def test_t_falls_back_per_key():
    assert t("ur", "no_such_key") == "no_such_key"
    assert t("xx", "positioning") == "Positioning"


def test_strategy_localized_all_locales():
    eng = _engine()
    markers = {
        "ur": "برانڈ حکمت عملی", "hi": "ब्रांड रणनीति",
        "es": "Estrategia de marca", "pt": "Estratégia de marca",
    }
    for code, marker in markers.items():
        out = eng._offline_smart_generate("Deliver the engagement output.",
                                          {**CTX, "agent": "strategist", "lang": code})
        assert marker in out, f"{code}: strategy not localized: {out[:100]}"
        assert "Brand Strategy" not in out
    en = eng._offline_smart_generate("Deliver the engagement output.",
                                     {**CTX, "agent": "strategist"})
    assert "Brand Strategy" in en  # default stays English


def test_copy_localized_urdu_and_hindi():
    eng = _engine()
    ur = eng._offline_smart_generate("Deliver the engagement output.",
                                     {**CTX, "agent": "copywriter", "lang": "ur"})
    assert "مہم کا مسودہ" in ur
    assert "خوش آمدید ای میل" in ur
    assert "Campaign Draft" not in ur

    hi = eng._offline_smart_generate("Deliver the engagement output.",
                                     {**CTX, "agent": "copywriter", "lang": "hi"})
    assert "अभियान का मसौदा" in hi
    assert "स्वागत ईमेल" in hi


def test_api_swarm_lang_roundtrip(client):
    r = client.post("/api/swarm/run", json={
        "campaign_name": "Urdu Chai", "product_name": "Chai House",
        "industry": "Cafe", "target_audience": "students",
        "key_benefits": "fresh, fast", "lang": "ur"})
    assert r.status_code == 200, r.text
    name = r.json()["campaign_name"]
    assert "برانڈ حکمت عملی" in r.json()["strategy_preview"]

    detail = client.get(f"/api/campaigns/{name}").json()
    assert "مہم کا مسودہ" in detail["copy"]["copy_text"]
    # persisted campaign carries the language it was generated in
    assert detail.get("lang") == "ur" or detail.get("meta", {}).get("lang") == "ur"


def test_api_swarm_unknown_lang_falls_back_to_en(client):
    r = client.post("/api/swarm/run", json={
        "campaign_name": "Fallback Chai", "product_name": "Chai House",
        "industry": "Cafe", "target_audience": "students",
        "key_benefits": "fresh, fast", "lang": "xx"})
    assert r.status_code == 200, r.text
    assert "Brand Strategy" in r.json()["strategy_preview"]
