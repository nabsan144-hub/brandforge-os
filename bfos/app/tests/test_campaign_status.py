def test_campaign_status_workflow_is_validated_and_persisted(client):
    created = client.post("/api/swarm/run", json={
        "campaign_name": "Workflow campaign", "product_name": "Apex Coffee",
        "industry": "Retail", "target_audience": "Remote workers", "key_benefits": "Fresh, clear pricing",
    })
    assert created.status_code == 200, created.text
    name = created.json()["campaign_name"]

    changed = client.put(f"/api/campaigns/{name}/status", json={"status": "internal_review"})
    assert changed.status_code == 200
    assert changed.json()["status"] == "internal_review"
    assert changed.json()["status_history"][-1]["status"] == "internal_review"

    detail = client.get(f"/api/campaigns/{name}").json()
    assert detail["status"] == "internal_review"
    assert client.put(f"/api/campaigns/{name}/status", json={"status": "published"}).status_code == 422
