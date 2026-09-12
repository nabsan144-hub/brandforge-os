// BrandForge OS — public waitlist endpoint (cloud, POST).
//
// The marketing site used to post to FormSubmit.co with a placeholder inbox
// (YOUR-EMAIL@gmail.com), so the form never actually captured a lead. That was
// a launch blocker (audit §1.1 / §1.4). This endpoint is the real backend the
// marketing waitlist posts to. It is intentionally unauthenticated (an email +
// a tier — no sensitive data), uses the service-role client to write into a
// dedicated `waitlist` table, and is CORS-open so it can be called cross-origin
// from www.brandforge-os.com.
//
// Table (migration 0005_waitlist.sql):  public.waitlist(id, email, tier, created_at)
//   email UNIQUE — a user signing up twice updates the row we already have.
import {readJson} from "../http.js";
import { admin } from "../sb.js";
import { serve } from "../serve.js";
import { rateLimit } from "../limit.js";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const TIER_SET = ["owner", "agency_source", "undecided"];

// Best-effort client IP (same logic as campaigns.js). Not security-critical —
// the waitlist is public + unauthenticated — used to cap abuse. The selected durable limiter fails closed on outages.
function clientIp(req) {
  const headers = req.headers;
  const get = (n) => (headers && typeof headers.get === "function" ? headers.get(n) : null);
  const vff = get("x-vercel-forwarded-for");
  if (vff) return vff.split(",").pop().trim();
  const real = get("x-real-ip");
  if (real) return real.trim();
  const ff = get("x-forwarded-for");
  if (ff) return ff.split(",").pop().trim();
  return "unknown";
}

function respond(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      ...CORS_HEADERS,
    },
  });
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

async function handle(req) {
  // CORS preflight (the marketing page is on a different origin). A 204 must
  // have no body.
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS_HEADERS });
  if (req.method !== "POST") return respond({ error: "Method not allowed" }, 405);

  // Cap per-IP abuse (10/hour) so a script can't flood the waitlist table.
  // Durable protection is required; an outage is a retryable 503.
  try {
  if (!(await rateLimit("waitlist-ip", clientIp(req), 10, 3600))) {
    return respond({ error: "Too many requests — please try again in a bit." }, 429);
  }

  } catch (e) { return respond({error:"Waitlist protection is temporarily unavailable. Please try later."},e.status||503); }

  let body;
  try {
    body = await readJson(req,4000);
  } catch {
    return respond({ error: "Invalid JSON" }, 400);
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return respond({ error: "Request body must be an object" }, 400);
  }

  // Honeypot: hidden field humans never fill. Pretend success, store nothing.
  if (body._honey) return respond({ ok: true, queued: false }, 200);

  const email = String(body.email || "").trim().toLowerCase();
  if (email.length>254 || !EMAIL_RE.test(email)) return respond({ error: "Enter a valid email address" }, 400);

  // Escape the tier before it reaches SQL-ish storage; fall back to "undecided".
  const tier = TIER_SET.includes(body.tier) ? String(body.tier) : "undecided";

  const sb = admin();
  const { data, error } = await sb
    .from("waitlist")
    .upsert({ email, tier }, { onConflict: "email" })
    .select("email")
    .single();

  if (error) {
    // 42P01 / PGRST205: the `waitlist` table has not been created yet. Return a
    // clear, actionable error instead of silently dropping the lead — the
    // client shows the support-email fallback.
    console.error("waitlist upsert failed", error.message);
    return respond(
      {
        error:
          error.code === "PGRST205" || /relation.*waitlist.*does not exist/i.test(error.message)
            ? "Waitlist is not enabled yet — email support@brandforge-os.com and we will add you to the list."
            : "Could not save your spot — email support@brandforge-os.com and we will add you to the list.",
      },
      501
    );
  }

  return respond({ ok: true, queued: true, email: data?.email }, 200);
}

const _h = serve(handle);
export default _h;
export const POST = _h;
export const OPTIONS = _h;
