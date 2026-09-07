#!/usr/bin/env node
/**
 * BrandForge OS — Live Site Smoke Test
 *
 * Fetches the live marketing site and asserts that the published HTML matches
 * the clean-URL scheme the repo ships:
 *   - every page returns 200
 *   - <link rel="canonical"> ===  https://www.brandforge-os.com/<clean-path>  (no
 *     `.html` suffix, always the `www` host)
 *   - og:url (when present) matches the same clean canonical
 *   - internal nav <a href> references do NOT use the stale `.html` suffix
 *
 * Why: catches "stale deploy / partial Vercel build / CDN edge cache" drift like
 * the one where pricing/tools/demo served old `.html` nav + apex canonicals
 * while the rest of the site was already clean.
 *
 * Usage:
 *   node scripts/live_site_smoke.js                # default base https://www.brandforge-os.com
 *   node scripts/live_site_smoke.js http://localhost:3000   # custom base (staging/preview)
 *   SITE_BASE=https://www.brandforge-os.com node scripts/live_site_smoke.js
 *
 * Exit code 0 = all pages clean; 1 = drift detected.
 *
 * NOTE: this is a network script — it is intentionally NOT part of the offline
 * `sales` test suite (npm test). Run it explicitly after a deploy.
 */

const BASE = (process.env.SITE_BASE || process.argv[2] || "https://www.brandforge-os.com")
  .replace(/\/+$/, "");

// The published canonical host. Because real pages always carry the production
// `www` canonical even when fetched from a preview/staging mirror, we compare
// against this fixed host (never the fetch BASE).
const fs=require('node:fs'), path=require('node:path');
const config=fs.readFileSync(path.join(__dirname,'../sales/assets/config.js'),'utf8');
const CANON_HOST=(config.match(/site_url:\s*['"]([^'"]+)['"]/)?.[1]||'https://www.brandforge-os.com').replace(/\/+$/,'');
function attribute(tag,name){return tag.match(new RegExp('\\b'+name+'=["\']([^"\']+)["\']','i'))?.[1]||null;}
function tagValue(text,tag,kind,key,value){
 for(const raw of text.match(new RegExp('<'+tag+'\\b[^>]*>','gi'))||[]){if(attribute(raw,kind)===key)return attribute(raw,value);}
 return null;
}

// The authoritative public URL list (must match sales/sitemap.xml exactly).
const PATHS = [
  "/", "/workspace", "/agents", "/pricing", "/tools",
  "/docs", "/demo", "/privacy", "/refund", "/terms",
];

// Stale schemes we must never see in a published page's canonicals or nav.
// Canonical host is always `www.` and paths never carry `.html`.
const STALE_HTML_RE = /href="[^"]*\.html"/g;
const APEX_CANONICAL_RE = /canonical" href="https:\/\/brandforge-os\.com\//;
const HTML_SUFFIX_RE = /\.html(?=["'])/;

function cleanPath(p) {
  const raw = p.replace(/^https?:\/\/[^/]+/, "/");
  return raw.endsWith("/") ? raw : raw.replace(/\.html$/, "");
}

async function fetchText(url) {
  const res = await fetch(url, {
    redirect: "follow",
    signal: AbortSignal.timeout(10000),
    headers: { "User-Agent": "brandforge-live-smoke/1.0" },
  });
  return { status: res.status, url: res.url, text: await res.text() };
}

(async () => {
  let failures = 0;
  const results = [];

  for (const path of PATHS) {
    const url = BASE + path;
    const expectedCanonical = CANON_HOST + cleanPath(path);
    let entry = { path, status: null, canonical: null, ogUrl: null, staleNav: 0, staleCanonical: false };

    try {
      const { status, text } = await fetchText(url);
      entry.status = status;

      entry.canonical = tagValue(text,'link','rel','canonical','href');
      entry.ogUrl = tagValue(text,'meta','property','og:url','content');

      // Stale scheme checks
      entry.staleNav = (text.match(STALE_HTML_RE) || []).filter(x=>!x.includes('assets/')).length; // any .html href in page
      entry.staleCanonical = APEX_CANONICAL_RE.test(text); // apex (non-www) canonical
      // og:url should match canonical host/clean form too
      if (entry.ogUrl) entry.ogStale = APEX_CANONICAL_RE.test(entry.ogUrl) || HTML_SUFFIX_RE.test(entry.ogUrl);

      // Assertions
      const checks = [];
      checks.push(["HTTP 200", status === 200]);
      checks.push(["canonical = expected", entry.canonical === expectedCanonical]);
      if (entry.ogUrl) checks.push(["og:url = canonical", entry.ogUrl === expectedCanonical]);
      checks.push(["no .html nav links", entry.staleNav === 0]);
      checks.push(["www canonical (no apex)", !entry.staleCanonical]);

      const bad = checks.filter(([, ok]) => !ok).map(([n]) => n);
      entry.pass = bad.length === 0;
      if (!entry.pass) {
        failures++;
        entry.problems = bad;
      }
    } catch (e) {
      failures++;
      entry.pass = false;
      entry.error = String(e && e.message || e);
    }
    results.push(entry);
  }

  // Render
  let ok = 0, fail = 0;
  for (const e of results) {
    const flag = e.pass ? "✅" : "❌";
    if (e.pass) ok++; else fail++;
    console.log(
      `${flag}  ${e.status || "ERR"}  ${e.path}` +
      (e.canonical ? `\n        canonical=${e.canonical}` : "") +
      (e.ogUrl ? `\n        og:url   =${e.ogUrl}` : "") +
      (e.problems ? `\n        DRIFT: ${e.problems.join(", ")}` : "") +
      (e.error ? `\n        ERROR: ${e.error}` : "")
    );
  }

  console.log(`\n${ok} clean / ${fail} drifted  (base: ${BASE})`);
  if (failures > 0) {
    console.error("LIVE SITE DRIFT DETECTED — redeploy the sales/ project so the build picks up the latest commit. Run again after deploy.");
    process.exit(1);
  }
  console.log("OK — live site matches clean-URL scheme.");
})();
