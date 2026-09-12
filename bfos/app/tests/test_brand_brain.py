from modules.claim_guard import review_marketing_copy


def test_claim_guard_reports_client_and_generic_risks():
    review = review_marketing_copy(
        "The best choice — guaranteed results for every customer.",
        "guaranteed, every customer",
    )
    assert review["status"] == "review_needed"
    assert any(item["type"] == "client_prohibited_phrase" for item in review["warnings"])
    assert any(item["type"] == "general_marketing_risk" for item in review["warnings"])


def test_brand_brain_update_is_persisted(client):
    clients = client.get("/api/clients").json()
    active = clients["active"]
    payload = {
        "client_name": active["client_name"],
        "industry": active.get("industry", "General"),
        "tone_of_voice": active.get("tone_of_voice", "Clear"),
        "target_audience": "Growing local businesses",
        "brand_promise": "Clear campaign strategy without invented claims",
        "proof_points": "Established in 2020; transparent pricing",
        "prohibited_claims": "guaranteed, number one",
        "primary_color": active.get("primary_color", "#E8B54A"),
        "secondary_color": active.get("secondary_color", "#0F172A"),
        "agency_brand": active.get("agency_brand", active["client_name"]),
    }
    response = client.put(f"/api/clients/{active['client_id']}", json=payload)
    assert response.status_code == 200, response.text
    saved = client.get("/api/clients").json()["active"]
    assert saved["brand_promise"] == payload["brand_promise"]
    assert saved["prohibited_claims"] == payload["prohibited_claims"]
