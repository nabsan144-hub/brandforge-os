// POST /api/campaigns/{id}/deliver — send an existing campaign pack link via
// WhatsApp (Stage 3). Generation is never touched; this is a separate
// post-generation service. Rate-limited per user (MAX_PER_HOUR).
import { admin, authUser, json } from "../sb.js";
import { WA_ENABLED, providerConfig, sendWhatsApp, validPhone, appUrl, MAX_PER_HOUR, deliveryAllowedForPlan } from "../deliver.js";
import {readJson} from "../http.js";
import { serve } from "../serve.js";

async function handle(req, ctx) {
  if (!WA_ENABLED()) return json({ error: "Delivery not enabled" }, 404);
  const user = await authUser(req);
  if (!user) return json({ error: "Not signed in" }, 401);
  const sb = admin();

  let id = ctx?.params?.id;
  if (!id) {
    try {
      id = new URL(req.url, "https://brandforge.local").pathname.split("/").filter(Boolean).slice(-2)[0];
    } catch {
      id = String(req.url || "").split("/").filter(Boolean).slice(-2)[0] || "";
    }
  }
  if (!id) return json({ error: "Campaign id required" }, 400);
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  // campaign must exist and belong to the user
  const { data: camp, error: cerr } = await sb
    .from("campaigns").select("id,name,product").eq("id", id).eq("user_id", user.id).single();
  if (cerr || !camp) return json({ error: "Campaign not found" }, 404);

  let body;
  try { body = await readJson(req, 4000); }
  catch(error) { return json({error:'Enter a valid reminder request.'},error.status||400); }
  try {
    const base=new URL(process.env.BRANDFORGE_APP_URL||'');
    if(base.protocol!=='https:'||base.username||base.password||base.search||base.hash)throw new Error();
  } catch { return json({error:'Workspace reminders are temporarily unavailable.'},503); }
  // authUser returns the Supabase AUTH user (id/email only) — profile columns
  // like whatsapp_phone are NOT on it, so fetch the saved phone from profiles.
  let savedPhone = "";
  const { data: prof, error: perr } = await sb
    .from("profiles").select("whatsapp_phone, plan").eq("id", user.id).single();
  // WhatsApp delivery is a storefront-promised Agency feature — do not let a
  // Free/Pro tenant trigger paid provider sends (or burn provider quota).
  if (perr || !prof) return json({error:"Could not verify your delivery entitlement."},503);
  if (!deliveryAllowedForPlan(prof.plan)) {
    return json({ error: "WhatsApp workspace reminders are available on Agency.", code: "PLAN_REQUIRED" }, 403);
  }
  if (!perr && prof && prof.whatsapp_phone) savedPhone = prof.whatsapp_phone;
  const phone = String(body.phone || "").trim() || savedPhone;
  if (!validPhone(phone)) return json({ error: "A valid E.164 phone number is required (e.g. +923001234567)." }, 400);

  // provider must be configured
  const provider = (process.env.WHATSAPP_PROVIDER || "").toLowerCase();
  if (!providerConfig(provider)) {
    return json({ error: "Workspace reminders are temporarily unavailable." }, 503);
  }

  // Reserve the delivery attempt under a DB advisory lock. A count-then-send
  // check was racy: concurrent requests could all observe the same remaining
  // allowance and exceed MAX_PER_HOUR.
  const { data: reservation, error: reservationError } = await sb.rpc("reserve_delivery_slot", {
    uid: user.id,
    cid: id,
    p: provider,
    max_per_hour: MAX_PER_HOUR,
  });
  if (reservationError) {
    console.error("delivery rate-limit reservation failed", reservationError);
    return json({ error: "Delivery service temporarily unavailable" }, 503);
  }
  if (!reservation?.ok) {
    if (reservation?.code === "LIMIT_HOURLY") {
      return json({ error: `Delivery rate limit reached (${MAX_PER_HOUR}/hour). Try again later.` }, 429);
    }
    return json({ error: "Delivery service temporarily unavailable" }, 503);
  }

  const variables = [String(camp.name || "campaign"), `${appUrl()}/app/c/${id}`];
  const reservationId = reservation.id;
  const mark = async (status) => {
    const { error } = await sb.from("delivery_log")
      .update({ status })
      .eq("id", reservationId)
      .eq("user_id", user.id);
    if (error) console.error(`delivery ${status} audit update failed`, error);
    return !error;
  };
  try {
    const result = await sendWhatsApp(provider, phone, variables);
    // The reservation row is already the audit record; mark it sent. If this
    // update fails, say so explicitly instead of claiming a complete audit.
    const auditLogged = await mark("sent");
    return json({ ok: true, provider: result.provider, to: phone, campaign: camp.id, note:"The link requires your own signed-in account; it does not grant client access.", audit_logged: auditLogged });
  } catch (e) {
    // Keep the reservation and mark the failed attempt. Counting it
    // conservatively avoids a retry storm if a provider accepted a message
    // just before returning an error.
    await mark("failed");
    return json({ error: "The reminder could not be confirmed. Check WhatsApp before retrying." }, 502);
  }
}

// Vercel routing adapter (dual-mode: legacy (req,res) OR Web Request->Response).
const _h = serve(handle);
export default _h;
export const POST = _h;
