def test_native_pdf_and_docx_exports(client):
    made = client.post('/api/swarm/run', json={'campaign_name':'Native export','product_name':'Apex Coffee','industry':'Retail','target_audience':'Remote workers','key_benefits':'Fresh coffee, clear pricing'})
    assert made.status_code == 200
    name = made.json()['campaign_name']
    pdf = client.get(f'/api/campaigns/{name}/export.pdf')
    docx = client.get(f'/api/campaigns/{name}/export.docx')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    assert docx.status_code == 200 and docx.content[:2] == b'PK'


def test_pdf_export_survives_angle_brackets_and_unclosed_tags():
    """HIGH-02 regression: '<' in LLM/copy text ('revenue < target', injected
    <font>/<b> markup, unclosed tags) must render as literal text, never as
    ReportLab formatting and never as a parser crash."""
    from modules.document_exporter import campaign_pdf, _pdf_safe

    assert _pdf_safe("a < b & c > d\nline2") == "a &lt; b &amp; c &gt; d<br/>line2"

    nasty = {
        "campaign_name": "Angle < Attack & Co",
        "status": "draft",
        "strategy": {"product_name": "P <q>", "strategy_text":
                     "Growth: 5 < 10 and <b>unclosed\n"
                     '<font size="200" color="red">HUGE INJECTED</font>'},
        "copy": {"copy_text": "React < Vue & Node > PHP <i>never closes"},
        "analysis": {"seo_analysis": "CTR < target: <br><br><b>b<b>b"},
    }
    payload = campaign_pdf(nasty)  # must not raise
    assert payload.startswith(b"%PDF")

    # And the route degrades to a clean 500 instead of an unhandled crash
    # if an exporter ever throws again (defense-in-depth).
    import server
    orig = server.campaign_pdf
    server.campaign_pdf = lambda c: (_ for _ in ()).throw(ValueError("boom"))
    try:
        from fastapi.testclient import TestClient
        with TestClient(server.app, raise_server_exceptions=False) as c:
            c.headers["X-BrandForge-Token"] = c.get("/api/session").json()["capability"]
            # seed a campaign through the real API, then hit the export route
            made = c.post('/api/swarm/run', json={'campaign_name': 'Broken pdf',
                                                  'product_name': 'X', 'industry': 'I',
                                                  'target_audience': 'A', 'key_benefits': 'b'})
            assert made.status_code == 200
            r = c.get(f"/api/campaigns/{made.json()['campaign_name']}/export.pdf")
            assert r.status_code == 500
            assert "PDF export failed" in r.text
    finally:
        server.campaign_pdf = orig


def test_generated_landing_and_ad_html_wellformed():
    """Regression: generated HTML deliverables must contain no stray
    backslashes and must keep class/href attributes intact (clients open
    these files outside any CSP)."""
    import re as _re
    from modules.visual_designer import VisualDesigner

    class _D:
        pass

    vd = VisualDesigner(_D())
    landing = vd.generate_landing_page("Test Cafe", "Food", "students", ["fresh", "fast"])
    assert "\\" not in landing
    assert 'class="hero">' in landing
    assert _re.search(r'href="[^"\\]+">', landing)
    ad = vd.generate_html_ad_card("Test Cafe", "An offer", ["fresh", "fast"])
    assert "\\" not in ad
    assert 'class="card">' in ad
