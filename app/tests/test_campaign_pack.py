def test_campaign_pack_creates_editable_approval_and_delivery_files(client):
    response = client.post("/api/swarm/run", json={
        "campaign_name": "Delivery Pack", "product_name": "Apex Coffee",
        "industry": "Retail", "target_audience": "Remote workers", "key_benefits": "Fresh coffee, transparent pricing",
    })
    assert response.status_code == 200, response.text
    name = response.json()["campaign_name"]
    detail = client.get(f"/api/campaigns/{name}").json()
    files = {item["name"]: item for item in detail["files"]}
    assert {"01_strategy_and_approval.html", "02_copy_pack.md", "03_content_calendar.csv", "04_creative_brief.md", "README_DELIVERY.md"} <= set(files)
    assert "Client Approval Summary" in files["01_strategy_and_approval.html"]["content"]
    assert "review_status" in files["03_content_calendar.csv"]["content"]
    assert "Campaign delivery" in files["README_DELIVERY.md"]["content"]
