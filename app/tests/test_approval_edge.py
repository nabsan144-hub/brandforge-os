"""Full-codebase-audit batch (1.2.19): approval-link hardening.

(1) Tokens are format-validated before ANY use — arbitrary path text can no
longer reach the meta-refresh attribute in the submit redirect.
(2) A live approval link whose campaign folder was deleted must yield a clean
404, not an AttributeError 500.
"""

import re


def _make_campaign(client, name="Approval edge"):
    made = client.post('/api/swarm/run', json={'campaign_name': name,
                                                'product_name': 'Apex Coffee', 'industry': 'Retail',
                                                'target_audience': 'Remote workers',
                                                'key_benefits': 'Fresh coffee'})
    assert made.status_code == 200
    return made.json()['campaign_name']


def test_approval_token_format_enforced(client):
    for bad in ("x", "shorTTok", "with space1234567890", "quote'inj-attempt-123456",
                "%3Cscript%3E12345678", "traversal/../../etc-12345678"):
        r = client.get(f"/approval/{bad}")
        assert r.status_code == 404, bad
        r2 = client.post(f"/approval/{bad}", data={"decision": "approved"})
        assert r2.status_code == 404, bad
    # PUT/DELETE API routes refuse malformed tokens identically
    r = client.put("/api/approvals/!!not-a-token-12345", json={"decision": "approved", "comment": ""})
    assert r.status_code == 404
    assert client.delete("/api/approvals/%3Cscript%3E-bad-token").status_code == 404


def test_approval_portal_survives_deleted_campaign(client, tmp_path):
    name = _make_campaign(client, "Gone campaign")
    created = client.post(f"/api/campaigns/{name}/approval-links")
    assert created.status_code == 200
    token = created.json()["token"]
    assert re.match(r"^[A-Za-z0-9_-]{16,128}$", token)

    # delete the campaign folder out from under the live link
    import server
    _, pm, _, _ = server.get_core()
    import shutil
    shutil.rmtree(pm._campaign_path(name), ignore_errors=True)

    r = client.get(f"/approval/{token}")
    assert r.status_code == 404
    assert "no longer exists" in r.text
    # submit still works (records the decision) and redirects to the portal
    r2 = client.post(f"/approval/{token}", data={"decision": "approved", "comment": "ok"})
    assert r2.status_code == 200


def test_approval_flow_end_to_end(client):
    name = _make_campaign(client, "Live approval flow")
    token = client.post(f"/api/campaigns/{name}/approval-links").json()["token"]
    r = client.get(f"/approval/{token}")
    assert r.status_code == 200 and "CLIENT REVIEW" in r.text
    r2 = client.post(f"/approval/{token}", data={"decision": "changes_requested", "comment": "tone < down"})
    assert r2.status_code == 200
    detail = client.get(f"/api/approvals/{token}").json()["approval"]
    assert detail["decision"] == "changes_requested"
    assert any("tone" in c["text"] for c in detail["comments"])
    assert client.delete(f"/api/approvals/{token}").json()["success"] is True
    assert client.get(f"/approval/{token}").status_code == 404
