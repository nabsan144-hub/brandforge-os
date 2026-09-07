def test_campaign_templates_are_available_and_safe(client):
    response = client.get("/api/campaign-templates")
    assert response.status_code == 200
    templates = response.json()["templates"]
    assert templates[0]["id"] == "blank"
    assert len(templates) >= 5
    for template in templates:
        assert set(template) == {
            "id", "name", "description", "campaign_name", "product_name",
            "industry", "target_audience", "key_benefits",
        }
        assert "<script" not in " ".join(template.values()).lower()
