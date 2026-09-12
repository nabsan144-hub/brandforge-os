import generationProgress from './_lib/routes/generation-progress.js';
import canvas from './_lib/routes/canvas.js';
import usageMetrics from './_lib/routes/usage-metrics.js';
import imageRecovery from './_lib/routes/image-recovery.js';
import transfers from './_lib/routes/transfers.js';
import review, {manageReview} from './_lib/routes/campaign-review.js';
import opsStatus from './_lib/routes/ops-status.js';
import campaignPreview from './_lib/routes/campaign-preview.js';
import campVisuals from './_lib/routes/camp-visuals.js';
import capabilities from './_lib/routes/capabilities.js';
import campAssets from './_lib/routes/camp-assets.js';
// BrandForge OS Cloud — single Vercel Function for every /api/* endpoint.
// Routed to ALL /api/* paths by the "/api/(.*)" -> "/api/index.js" rewrite in
// vercel.json (added after PR #a06486c: the [...slug].js filesystem catch-all
// only received single-segment paths; nested routes hit platform 404).
//
// WHY THIS FILE EXISTS (Vercel Hobby constraint):
//   With the frameworkless api/ directory, every file under api/ becomes its
//   own Vercel Function, and the Hobby plan allows at most 12 Functions per
//   deployment. This backend has 23 endpoints, so per-file functions cannot
//   deploy on Hobby (error: "No more than 12 serverless functions can be added
//   to a deployment on the Hobby plan").
//
//   Solution: all route logic lives in api/_lib/routes/*.js (underscore dirs
//   are never treated as Functions), and this one catch-all — api/[...slug].js
//   — dispatches by URL to the matching handler. Each handler keeps its exact
//   original logic and reads req.url / ctx itself, so behaviour is identical
//   to one-function-per-file. api/health.js, api/maintenance.js,
//   api/paddle-webhook.js and api/waitlist.js stay as thin re-export files so
//   those four critical paths are also their own small Functions (exact files
//   take precedence over the catch-all), still well under the 12-Function cap.
//
//   Count check: 1 catch-all + 4 re-export files = 5 Functions ≤ 12 (Hobby OK).
//
// Usage per route module: default export = serve(handler) plus named HTTP
// method exports, exactly as when each route was its own api/*.js file.
import {serve} from './_lib/serve.js';
import health from './_lib/routes/health.js';
import maintenance from './_lib/routes/maintenance.js';
import waitlist from './_lib/routes/waitlist.js';
import brands from './_lib/routes/brands.js';
import campaigns from './_lib/routes/campaigns.js';
import campId from './_lib/routes/camp-id.js';
import campIdDeliver from './_lib/routes/camp-id-deliver.js';
import config from './_lib/routes/config.js';
import feedback from './_lib/routes/feedback.js';
import me from './_lib/routes/me.js';
import meExport from './_lib/routes/me-export.js';
import meKeys from './_lib/routes/me-keys.js';
import paddleWebhook from './_lib/routes/paddle-webhook.js';
import billCancelPending from './_lib/routes/bill-cancel-pending.js';
import billChange from './_lib/routes/bill-change.js';
import billCheckout from './_lib/routes/bill-checkout.js';
import billClientToken from './_lib/routes/bill-client-token.js';
import billPortal from './_lib/routes/bill-portal.js';
import billReconcile from './_lib/routes/bill-reconcile.js';
import billStatus from './_lib/routes/bill-status.js';
import deskCheckout from './_lib/routes/desk-checkout.js';
import deskDownload from './_lib/routes/desk-download.js';
import deskResend from './_lib/routes/desk-resend.js';

// Exact-path endpoints (same URLs the app and marketing site always called).
const EXACT = new Map([
  ['/api/capabilities', capabilities],
  ['/api/health', health],
  ['/api/ops-status', opsStatus],
  ['/api/maintenance', maintenance],
  ['/api/waitlist', waitlist],
  ['/api/brands', brands],
  ['/api/campaigns', campaigns],
  ['/api/generation-progress',generationProgress],
  ['/api/campaign-preview', campaignPreview],
  ['/api/config', config],
  ['/api/feedback', feedback],
  ['/api/review', review],
  ['/api/transfers', transfers],
  ['/api/canvas', canvas],
  ['/api/usage-metrics', usageMetrics],
  ['/api/me', me],
  ['/api/me/export', meExport],
  ['/api/me/keys', meKeys],
  ['/api/paddle-webhook', paddleWebhook],
  ['/api/billing/cancel-pending', billCancelPending],
  ['/api/billing/change', billChange],
  ['/api/billing/checkout', billCheckout],
  ['/api/billing/paddle-client-token', billClientToken],
  ['/api/billing/portal', billPortal],
  ['/api/billing/reconcile', billReconcile],
  ['/api/billing/status', billStatus],
  ['/api/desktop/checkout', deskCheckout],
  ['/api/desktop/download', deskDownload],
  ['/api/desktop/resend', deskResend],
]);

// URL-parameter endpoints: [regex, paramName, handler]. Order matters — more
// specific (deeper) patterns first. Each handler already parses req.url as a
// fallback; ctx.params is supplied for parity with per-file Vercel routing.
const DYNAMIC = [
  [/^\/api\/campaigns\/([^/]+)\/image-recovery$/, 'id', imageRecovery],
  [/^\/api\/campaigns\/([^/]+)\/review$/, 'id', manageReview],
  [/^\/api\/campaigns\/([^/]+)\/visuals$/, 'id', campVisuals],
  [/^\/api\/campaigns\/([^/]+)\/assets$/, 'id', campAssets],
  [/^\/api\/campaigns\/([^/]+)\/deliver$/, 'id', campIdDeliver],
  [/^\/api\/campaigns\/([^/]+)$/, 'id', campId],
];

function notFound() {
  return new Response(JSON.stringify({error: 'Not found'}), {
    status: 404,
    headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'},
  });
}

async function dispatch(req, ctx) {
  let path;
  try {
    path = new URL(req.url, 'https://brandforge.local').pathname;
  } catch {
    return notFound();
  }
  if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1);
  let fn = EXACT.get(path);
  let params;
  if (!fn) {
    for (const [re, paramName, handler] of DYNAMIC) {
      const m = re.exec(path);
      if (m) {
        fn = handler;
        try { params = {[paramName]: decodeURIComponent(m[1])}; } catch { params = {[paramName]: m[1]}; }
        break;
      }
    }
  }
  if (!fn) return notFound();
  // Forward the ORIGINAL request unchanged plus an optional {params} context.
  // Each route default is serve(handler): in Web mode it passes through; in
  // legacy Node mode the outer serve() below already converted (req, res) into
  // a Web Request, so handlers always run in Web style — same as before.
  return fn(req, params ? {...(ctx || {}), params} : ctx);
}

// Every HTTP method routes through the same dispatcher (each route enforces
// its own allowed methods and CORS preflight, exactly as per-file before).
const h = serve(dispatch);
export default h;
export const GET = h;
export const POST = h;
export const PUT = h;
export const PATCH = h;
export const DELETE = h;
export const OPTIONS = h;
export const HEAD = h;
