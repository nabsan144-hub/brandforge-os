import os


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["tools_count"] == 21
    assert d["license"]["mode"] == "local" and d["license"]["licensed"] is True


def test_swarm_and_detail_flow(client):
    r = client.post("/api/swarm/run", json={
        "campaign_name": "Api Test Camp", "product_name": "BlueBrew",
        "industry": "Coffee", "target_audience": "Remote workers",
        "key_benefits": "fast, organic"})
    assert r.status_code == 200, r.text
    d = r.json()
    name = d["campaign_name"]
    assert name == "api_test_camp"

    r2 = client.get(f"/api/campaigns/{name}")
    assert r2.status_code == 200
    c = r2.json()
    assert c["strategy"]["product_name"] == "BlueBrew"
    assert any(f["name"] == "hero_banner.svg" for f in c["files"])

    r3 = client.get(f"/api/campaigns/{name}/files/hero_banner.svg")
    assert r3.status_code == 200 and r3.text.startswith("<svg")

    r4 = client.get(f"/api/campaigns/{name}/download")
    assert r4.status_code == 200 and r4.content[:2] == b"PK"

    assert client.get("/api/campaigns/does_not_exist").status_code == 404


def test_xss_escaped_in_outputs(client):
    r = client.post("/api/swarm/run", json={
        "campaign_name": "xss probe", "product_name": "<script>alert(1)</script>",
        "industry": "<img src=x onerror=alert(1)>", "target_audience": "a",
        "key_benefits": "b"})
    assert r.status_code == 200
    name = r.json()["campaign_name"]
    svg = client.get(f"/api/campaigns/{name}/files/hero_banner.svg").text
    assert "<script>alert(1)</script>" not in svg
    report = client.get(f"/api/campaigns/{name}").json()
    md = next((f.get("content", "") for f in report["files"] if f["name"] == "campaign_report.md"), "")
    assert "<script>alert" not in md


def test_traversal_slugged(client):
    r = client.post("/api/swarm/run", json={
        "campaign_name": "../../../etc/passwd", "product_name": "p",
        "industry": "i", "target_audience": "a", "key_benefits": "b"})
    assert r.status_code == 200
    assert r.json()["campaign_name"] == "etc_passwd"
    assert not os.path.exists("/etc/passwd_brandforge")


def test_settings_validation(client):
    assert client.post("/api/settings", json={"provider": "groq"}).status_code == 400
    assert client.post("/api/settings", json={"provider": "bogus"}).status_code == 400
    assert client.post("/api/settings", json={"provider": "offline"}).status_code == 200


def test_chat_offline(client):
    r = client.post("/api/chat", json={"message": "Product: Apex Coffee, Industry: Retail, Audience: pros, Benefits: organic, fast"})
    assert r.status_code == 200
    d = r.json()
    assert d["provider"] == "offline"
    assert "Apex Coffee" in d["brandforge_response"]


def test_memory_recorded(client):
    assert client.post("/api/chat", json={"message":"Remember this local test conversation."}).status_code == 200
    r = client.get("/api/memory")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_clients(client):
    r = client.get("/api/clients")
    assert r.status_code == 200 and r.json()["count"] >= 1
    r2 = client.post("/api/clients", json={"client_name": "../../etc/cron", "industry": "x"})
    assert r2.status_code == 200
    assert r2.json()["client_id"] == "etc_cron"


def test_license_endpoint(client):
    r = client.get("/api/license")
    assert r.status_code == 200
    assert r.json()["mode"] == "local"


def test_version_consistency(client):
    """Version must agree across /health, server source, pyproject and CHANGELOG
    (drift here shipped 1.1.0 labels on a 1.2.x product)."""
    import re
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    health_v = client.get("/health").json()["version"]
    from version_info import __version__ as src_v
    import server
    assert server.__version__ == src_v
    pm = re.search(r'^version = "([\d.]+)"',
                   open(os.path.join(app_dir, "pyproject.toml")).read(), re.M)
    assert pm and pm.group(1) == src_v, "pyproject.toml version != server __version__"
    ch = open(os.path.join(root, "CHANGELOG.md")).read()
    top = re.search(r"^## ([\d.]+)", ch, re.M)
    assert top, "CHANGELOG missing"
    assert top.group(1) == src_v, f"CHANGELOG top {top.group(1)} != {src_v}"
    assert health_v == src_v


def test_websocket_roundtrip(client):
    """WS replies must be valid JSON (was repr() in v1.0)."""
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_text()
        import json as _json
        d0 = _json.loads(first)
        assert d0["type"] == "connected"
        ws.send_text("Product: Apex Coffee, Industry: Retail, Audience: pros, Benefits: organic, fast")
        d1 = _json.loads(ws.receive_text())
        assert d1["type"] == "response"
        assert "Apex Coffee" in d1["message"]
