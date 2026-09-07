#!/usr/bin/env node
/**
 * BrandForge OS — Live CLOUD API Smoke Test
 *
 * Why this exists:
 *   On 2026-09-06 the Vercel Hobby refactor (one catch-all function via
 *   api/[...slug].js) deployed "successfully", but Vercel's filesystem router
 *   only forwarded SINGLE-segment /api/* paths to it. Every nested endpoint —
 *   /api/billing/*, /api/desktop/*, /api/me/keys, /api/me/export,
 *   /api/campaigns/[id], /api/campaigns/[id]/deliver — returned the Vercel
 *   PLATFORM 404 ("The page could not be found / NOT_FOUND"). Unit tests,
 *   vitest and the marketing smoke test could not see it. Checkout, campaign
 *   detail, pack download, key management and account export were dead in
 *   production for paying-intent users.
 *
 *   This script catches exactly that class of failure: after every deploy,
 *   it hits every endpoint path shape and asserts the RESPONSE CAME FROM THE
 *   APP (JSON envelope or handler error), never from the platform 404 page.
 *
 * Usage:
 *   node scripts/live_api_smoke.mjs                       # prod app origin
 *   node scripts/live_api_smoke.mjs https://preview-xyz.vercel.app
 *   API_BASE=https://app.brandforge-os.com node scripts/live_api_smoke.mjs
 *
 * Exit code 0 = every route reached the app; 1 = platform 404 or unexpected.
 */

const BASE = (process.env.API_BASE || process.argv[2] || "https://app.brandforge-os.com").replace(/\/+$/, "");

// [method, path, expectedStatusCodes]. Unauthenticated probes: handlers reply
// 401/405/400 with the APP's JSON envelope. Any Vercel platform 404 is a fail.
const ROUTES = [
  ["GET", "/api/health", [200]],
  ["GET", "/api/config", [200]],
  ["GET", "/api/waitlist", [405]],
  ["GET", "/api/paddle-webhook", [405]],
  ["GET", "/api/maintenance", [401, 405]],
  ["GET", "/api/brands", [401, 405]],
  ["GET", "/api/campaigns", [401, 405]],
  ["GET", "/api/feedback", [401, 405]],
  ["GET", "/api/me", [401, 405]],
  // single-segment catch-all fallback must return the APP's JSON 404, not platform
  ["GET", "/api/no-such-endpoint-bf-smoke", [404]],
  // nested paths — the class that broke in production on 2026-09-06
  ["GET", "/api/me/keys", [401, 405]],
  ["GET", "/api/me/export", [401, 405]],
  ["GET", "/api/billing/status", [401, 405]],
  ["POST", "/api/billing/checkout", [401, 405]],
  ["POST", "/api/billing/change", [401, 405]],
  ["POST", "/api/billing/portal", [401, 405]],
  ["POST", "/api/billing/reconcile", [401, 405]],
  ["POST", "/api/billing/cancel-pending", [401, 405]],
  ["GET", "/api/billing/paddle-client-token", [200, 401, 405, 503]],
  ["POST", "/api/desktop/checkout", [400, 401, 405, 503]],
  ["POST", "/api/desktop/download", [400, 401, 405]],
  ["POST", "/api/desktop/resend", [400, 401, 405]],
  ["GET", "/api/campaigns/00000000-0000-0000-0000-000000000000", [401, 405]],
  ["POST", "/api/campaigns/00000000-0000-0000-0000-000000000000/deliver", [401, 405]],
  // nested fallback must also be the app's JSON 404
  ["GET", "/api/billing/no-such-bf-smoke", [404]],
];

const PLATFORM_404 = /The page could not be found|^NOT_FOUND$/m;

(async () => {
  let failures = 0;
  console.log(`BrandForge live API smoke → ${BASE}\n`);
  for (const [method, path, okStatuses] of ROUTES) {
    let status = 0, body = "";
    try {
      const res = await fetch(BASE + path, {
        method,
        redirect: "manual",
        signal: AbortSignal.timeout(15000),
        headers: { "User-Agent": "brandforge-api-smoke/1.0", "Content-Type": "application/json" },
        ...(method === "POST" ? { body: "{}" } : {}),
      });
      status = res.status;
      body = (await res.text()).slice(0, 400);
    } catch (e) {
      console.log(`FAIL  ${method} ${path}  — network error: ${e.message}`);
      failures++;
      continue;
    }
    const platform404 = status === 404 && PLATFORM_404.test(body);
    const statusOk = okStatuses.includes(status);
    if (platform404 || !statusOk) {
      console.log(`FAIL  ${method} ${path}  — ${status} ${platform404 ? "PLATFORM 404 (route never reached the function!)" : "unexpected status"} :: ${body.replace(/\s+/g, " ").slice(0, 90)}`);
      failures++;
    } else {
      console.log(`ok    ${method} ${path}  — ${status}`);
    }
  }
  console.log(failures ? `\n${failures} route(s) broken — do NOT announce/checkout-promote this deploy.` : "\nAll API routes reach the app.");
  process.exit(failures ? 1 : 0);
})();
