// WhatsApp delivery (Stage 3) — post-generation, separate service.
// The generation pipeline is NEVER modified; this module only sends an
// existing campaign's pack link via a WhatsApp Business API provider.
// Providers: twilio | 360dialog. Feature flag: WA_DELIVERY_ENABLED=1.
// Domain-agnostic: appUrl() uses BRANDFORGE_APP_URL env var — set to your
// actual deployed domain (any host: free preview host, custom .com/.pk, etc).
// If not set, falls back to https://brandforge-os.com as example — you MUST
// set BRANDFORGE_APP_URL for any other domain.

export const MAX_PER_HOUR = 10;

// WhatsApp delivery is advertised as an Agency-tier feature on the storefront
// ("Optional WhatsApp campaign delivery"). Gate it to the paid tiers that
// promise it so a Free/Pro user cannot trigger paid provider sends. The
// Desktop ownership has no Cloud messaging entitlement.
export const WA_PLANS = ["agency"];
export const deliveryAllowedForPlan = (plan) => WA_PLANS.includes(String(plan || "").toLowerCase());

export const WA_ENABLED = () => process.env.WA_DELIVERY_ENABLED === "1";

export function providerConfig(provider) {
  if (provider === "twilio") {
    const sid = process.env.TWILIO_ACCOUNT_SID || "";
    const token = process.env.TWILIO_AUTH_TOKEN || "";
    const templateSid = process.env.TWILIO_WHATSAPP_TEMPLATE_SID || "";
    const from = process.env.TWILIO_WHATSAPP_FROM || "whatsapp:+14155238886";
    return sid && token && templateSid ? { sid, token, templateSid, from } : null;
  }
  if (provider === "360dialog") {
    const token = process.env.WABA_360DIALOG_TOKEN || "";
    const ns = process.env.WABA_NAMESPACE || "";
    const name = process.env.WABA_TEMPLATE_NAME || "";
    const lang = process.env.WABA_TEMPLATE_LANG || "en";
    return token && ns && name ? { token, ns, name, lang } : null;
  }
  return null;
}

export function appUrl() {
  // Domain-agnostic: operator sets BRANDFORGE_APP_URL to any domain
  // Example: https://your-deployment-host or https://app.yourdomain.com
  // Falls back to https://brandforge-os.com as example placeholder
  return (process.env.BRANDFORGE_APP_URL || process.env.BRANDFORGE_MARKETING_URL || "https://brandforge-os.com").replace(/\/+$/, "");
}

const E164 = /^\+[1-9]\d{1,14}$/;
export function validPhone(p) {
  return E164.test(String(p || "").trim());
}

// Provider-agnostic send. Returns { ok: true } or throws with a message.
export async function sendWhatsApp(provider, to, variables) {
  const cfg = providerConfig(provider);
  if (!cfg) throw new Error("WhatsApp provider not configured");
  const phone = String(to).trim();

  if (provider === "twilio") {
    const url = `https://api.twilio.com/2010-04-01/Accounts/${cfg.sid}/Messages.json`;
    const body = new URLSearchParams({
      From: cfg.from,
      To: `whatsapp:${phone}`,
      ContentSid: cfg.templateSid,
      ContentVariables: JSON.stringify({ "1": variables[0], "2": variables[1] }),
    });
    const r = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: "Basic " + Buffer.from(`${cfg.sid}:${cfg.token}`).toString("base64"),
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body.toString(),
      signal: AbortSignal.timeout(15000),
    });
    if (!r.ok) throw new Error(`twilio ${r.status}`);
    return { ok: true, provider: "twilio" };
  }

  // 360dialog (WABA provider API)
  const url = "https://waba.360dialog.io/v1/messages";
  const payload = {
    to: phone,
    type: "template",
    template: {
      namespace: cfg.ns,
      name: cfg.name,
      language: { code: cfg.lang, policy: "deterministic" },
      components: [
        {
          type: "body",
          parameters: [
            { type: "text", text: variables[0] },
            { type: "text", text: variables[1] },
          ],
        },
      ],
    },
  };
  const r = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${cfg.token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(15000),
  });
  if (!r.ok) throw new Error(`360dialog ${r.status}`);
  return { ok: true, provider: "360dialog" };
}
