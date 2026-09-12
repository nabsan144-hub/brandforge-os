"""Sales-site & cloud-SPA integrity tests (v1.2.23 full audit).

The 291 backend tests didn't cover the marketing pages — this pass found a
dead waitlist form, a script-order bug that froze the pricing badge at
"LAUNCHING SOON", and cloud SPA calls missing their auth header. These static
checks pin all three classes so they can't return.
"""

import os
import re
import glob
from urllib.parse import unquote, urlsplit

SALES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "..", "sales")
CLOUD_SPA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "..", "cloud", "public", "index.html")
CLOUD_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "..", "cloud", "public", "app.js")


def _cloud_src():
    """The cloud SPA is intentionally split: markup in index.html, app logic in
    app.js (externalized so the CSP can drop 'unsafe-inline'). Tests that check
    behavior should read both.""" 
    with open(CLOUD_SPA, encoding="utf-8") as f:
        html = f.read()
    try:
        with open(CLOUD_APP, encoding="utf-8") as f:
            html += "\n" + f.read()
    except FileNotFoundError:
        pass
    return html


def _sales(name):
    with open(os.path.join(SALES, name), encoding="utf-8") as f:
        return f.read()


def test_every_referenced_sales_asset_exists():
    assert os.path.exists(os.path.join(SALES, "vercel.json")), "Vercel static-site config must be shipped with the sales root"
    for page in glob.glob(os.path.join(SALES, "*.html")):
        html = open(page, encoding="utf-8").read()
        for m in re.finditer(r'(?:src|href|poster)="(assets/[^"]+)"', html):
            # Query/fragment state belongs to the URL, not the on-disk filename.
            path = os.path.join(SALES, unquote(urlsplit(m.group(1)).path))
            assert os.path.isfile(path), f"{os.path.basename(page)} references missing asset: {m.group(1)}"
    netlify = open(os.path.join(SALES, "netlify.toml"), encoding="utf-8").read()
    headers = open(os.path.join(SALES, "_headers"), encoding="utf-8").read()
    assert "assets/config.js" in netlify and "no-store" in netlify
    assert "/assets/config.js" in headers and "no-store" in headers


def test_waitlist_form_is_wired():
    html = _sales("pricing.html")
    # the form markup
    assert 'id="waitlist-form"' in html
    assert 'name="_honey"' in html
    # ...and the handler that actually submits it
    assert 'assets/waitlist.js' in html, "waitlist.js must be loaded on the pricing page"
    js = open(os.path.join(SALES, "assets", "waitlist.js"), encoding="utf-8").read()
    assert "waitlist-form" in js and "addEventListener('submit'" in js
    # The waitlist posts to the real cloud /api/waitlist backend (no FormSubmit
    # placeholder, no dead form). config.js resolves the endpoint from hosted_url.
    assert "waitlistEndpoint" in js, "handler must resolve and POST a real waitlist endpoint"
    assert "formsubmit.co/ajax" not in js, "FormSubmit placeholder must be gone"
    config = open(os.path.join(SALES, "assets", "config.js"), encoding="utf-8").read()
    assert "/api/waitlist" in config, "config must derive the /api/waitlist endpoint"
    assert "YOUR-EMAIL" not in config, "placeholder waitlist inbox must be gone"


def test_pricing_config_loads_before_launch_state_script():
    html = _sales("pricing.html")
    cfg_pos = html.find('src="assets/config.js"')
    swap_pos = html.find("Launch-state badge")
    assert cfg_pos != -1 and swap_pos != -1
    assert cfg_pos < swap_pos, "config.js must load BEFORE the launch-state script reads BRANDFORGE_LAUNCH"


def test_nav_shows_signin_startfree_no_version_pill():
    # v1.5.1 intentionally removed the nav version pill in favor of
    # Sign in / Start free links — this guards against re-introducing a stale
    # hardcoded version string in the nav.
    import server
    html = _sales("index.html")
    assert "app.brandforge-os.com/login" in html, "nav must have a Sign in link"
    assert "app.brandforge-os.com/signup" in html, "nav must have a Start free link"
    assert f"v{server.__version__} • local-first" not in html, "version pill was removed in v1.5.1 — do not re-add it"


def test_canonical_and_og_on_public_pages():
    for name in ("index.html", "pricing.html", "agents.html", "docs.html",
                 "workspace.html", "tools.html", "privacy.html", "terms.html", "refund.html"):
        html = _sales(name)
        assert 'rel="canonical"' in html, f"{name}: missing canonical"
        assert 'property="og:url"' in html, f"{name}: missing og:url"
        assert 'name="description"' in html, f"{name}: missing meta description"


def test_404_is_noindex():
    assert 'name="robots" content="noindex"' in _sales("404.html")


def _prod_origin():
    """Expected production origin = committed config.js site_url (falls back
    to the legacy custom domain), so the check adapts to wherever you deploy."""
    cfg = open(os.path.join(SALES, "assets", "config.js"), encoding="utf-8").read()
    m = re.search(r"site_url:\s*'([^']+)'", cfg)
    return (m.group(1) if m else "https://brandforge-os.com").rstrip("/")


def test_sitemap_lists_all_public_pages():
    sitemap = open(os.path.join(SALES, "sitemap.xml"), encoding="utf-8").read()
    # homepage is the bare root URL (correct sitemap practice)
    assert _prod_origin() + "/</loc>" in sitemap, "sitemap missing the homepage"
    assert "404.html" not in sitemap, "404 must not be in the sitemap"


def test_cloud_spa_authenticated_calls_use_api_helper():
    """Every /api call that needs auth must go through api() (Bearer header).

    The public config + Paddle token endpoints are the only raw-fetch
    exceptions (they need no session).
    """
    html = _cloud_src()
    for m in re.finditer(r'fetch\((["\'])(/api/[^"\']+)\1', html):
        call = m.group(0)
        assert m.group(2) in ('/api/config', '/api/billing/paddle-client-token'), \
            f"raw fetch to protected endpoint must use api(): {call}"


def test_cloud_spa_paddle_initialized_once():
    html = _cloud_src()
    # Canonical identifier is `__bfPaddleInit` (BrandForge, not the legacy
    # Vanguard name). Kept as a substring check so a regression that drops
    # the double-init guard is caught.
    assert ("__bfPaddleInit" in html) or ("__vgPaddleInit" in html), \
        "Paddle.Initialize must be guarded against double-init"


def test_cloud_spa_refreshes_auth_and_can_reach_billing():
    html = _cloud_src()
    assert "onAuthStateChange" in html
    assert "currentSession = nextSession" in html
    assert 'id="bill-back"' in html
    assert "billing-mode" in html
    assert 'Paddle.Initialize({' in html
    assert 'eventCallback:' in html
