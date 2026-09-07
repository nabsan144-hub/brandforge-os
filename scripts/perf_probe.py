"""Sales-page performance/SEO probe. Serve sales/ on :8125, then run."""
import json
import time
import os

from playwright.sync_api import sync_playwright

PAGES = ["index.html","pricing.html","agents.html","workspace.html","docs.html"]
with sync_playwright() as pw:
    b = pw.chromium.launch()
    out = {}
    for p in PAGES:
        page = b.new_page()
        sizes = []
        page.on("response", lambda r, s=sizes: s.append(int(r.headers.get("content-length") or 0)))
        t0 = time.time()
        page.goto(os.environ.get("BRANDFORGE_SALES_QA_URL", "http://127.0.0.1:8765").rstrip("/")+"/"+p, wait_until="load")
        dt = round(time.time() - t0, 2)
        ld = page.evaluate("""() => [...document.querySelectorAll('script[type="application/ld+json"]')]
            .map(s => { try { JSON.parse(s.textContent); return 'ok'; } catch(e) { return 'INVALID'; } })""")
        out[p] = {"response_header_KB": round(sum(sizes)/1024,1), "reqs": len(sizes), "load_s": dt,
                  "ldjson": ld,
                  "title": page.evaluate("document.title.length"),
                  "desc": page.evaluate("(document.querySelector('meta[name=description]')||{}).content?.length || 0")}
        page.close()
    print(json.dumps(out, indent=1))
    b.close()
