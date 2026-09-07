"""Phase 6 (§6.2): client-facing approval portal v2 — deliverables grid,
sandboxed landing pages, per-asset comments, file route hardening, inbox."""


def _make_campaign(client, name):
    r = client.post("/api/swarm/run", json={
        "campaign_name": name, "product_name": "Portal Bread",
        "industry": "Bakery", "target_audience": "Morning commuters",
        "key_benefits": "Fresh daily"})
    assert r.status_code == 200, r.text
    return r.json()["campaign_name"]


def _portal(client, name):
    r = client.post(f"/api/campaigns/{name}/approval-links")
    assert r.status_code == 200
    return r.json()["token"]


def test_portal_renders_deliverables_grid_and_sandboxed_pages(client):
    name = _make_campaign(client, "Portal v2")
    token = _portal(client, name)
    page = client.get(f"/approval/{token}")
    assert page.status_code == 200
    body = page.text
    # visuals render as images through the token-scoped file route
    assert f'/approval/{token}/file/hero_banner.svg' in body
    assert "<img " in body
    # landing page renders in a script-free sandbox
    assert 'iframe sandbox=""' in body
    # per-asset comment selector lists deliverables
    assert 'name="asset"' in body and "hero_banner.svg" in body


def test_file_route_serves_images_and_blocks_traversal(client):
    name = _make_campaign(client, "Portal files")
    token = _portal(client, name)
    ok = client.get(f"/approval/{token}/file/hero_banner.svg")
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("image/svg+xml")

    assert client.get(f"/approval/{token}/file/..%2F..%2Fserver.py").status_code == 404
    assert client.get(f"/approval/{token}/file/%2e%2e%2fetc%2fpasswd").status_code == 404
    assert client.get(f"/approval/{token}/file/campaign.json").status_code == 404  # filtered
    # non-image deliverables download as attachments
    doc = client.get(f"/approval/{token}/file/report.md")
    if doc.status_code == 200:
        assert doc.headers["content-disposition"] == "attachment"


def test_per_asset_comment_is_stored_and_rendered(client):
    name = _make_campaign(client, "Portal asset comment")
    token = _portal(client, name)
    post = client.post(f"/approval/{token}", data={
        "decision": "", "comment": "Make the banner warmer", "asset": "hero_banner.svg"})
    assert post.status_code == 200
    page = client.get(f"/approval/{token}").text
    assert "Make the banner warmer" in page
    assert "[hero_banner.svg]" in page.replace("&#x27;", "'") or "hero_banner.svg]" in page


def test_legacy_comment_without_asset_still_renders(client):
    name = _make_campaign(client, "Portal legacy")
    token = _portal(client, name)
    client.post(f"/approval/{token}", data={"decision": "", "comment": "Old style note", "asset": ""})
    assert "Old style note" in client.get(f"/approval/{token}").text


def test_revoked_token_loses_file_access(client):
    name = _make_campaign(client, "Portal revoke")
    token = _portal(client, name)
    assert client.get(f"/approval/{token}/file/hero_banner.svg").status_code == 200
    get_approvals = client.app.state  # noqa: F841  (documentation of intent only)
    import server
    server.get_approvals().revoke(token)
    assert client.get(f"/approval/{token}").status_code == 404
    assert client.get(f"/approval/{token}/file/hero_banner.svg").status_code == 404


def test_inbox_lists_open_links_with_status(client):
    name = _make_campaign(client, "Portal inbox")
    token = _portal(client, name)
    inbox = client.get("/api/approvals").json()["approvals"]
    row = next((r for r in inbox if r["campaign"] == name), None)
    assert row is not None, inbox[:3]
    assert row["decision"] == "pending"
    assert row["token"] == token  # desktop-local stores tokens for reopen
    client.post(f"/approval/{token}", data={"decision": "approved", "comment": "Ship it"})
    inbox = client.get("/api/approvals").json()["approvals"]
    row = next(r for r in inbox if r["campaign"] == name)
    assert row["decision"] == "approved"
    assert row["last_comment"] == "Ship it"
