def test_campaign_revision_keeps_source_and_starts_a_new_draft(client):
    created = client.post("/api/swarm/run", json={
        "campaign_name": "Revision source", "product_name": "Apex Coffee",
        "industry": "Retail", "target_audience": "Remote workers", "key_benefits": "Fresh, clear pricing",
    })
    assert created.status_code == 200, created.text
    source = created.json()["campaign_name"]
    client.put(f"/api/campaigns/{source}/status", json={"status": "approved"})

    revision = client.post(f"/api/campaigns/{source}/revisions")
    assert revision.status_code == 200, revision.text
    data = revision.json()
    assert data["name"] == "revision_source_v2"
    assert data["revision_of"] == source
    assert data["revision_number"] == 2
    assert data["status"] == "draft"

    original = client.get(f"/api/campaigns/{source}").json()
    revised = client.get(f"/api/campaigns/{data['name']}").json()
    assert original["status"] == "approved"
    assert revised["status"] == "draft"
    assert revised["revision_of"] == source
    assert any(item["name"] == "hero_banner.svg" for item in revised["files"])
