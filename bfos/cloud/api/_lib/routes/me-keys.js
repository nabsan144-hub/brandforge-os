// BYOK key management — Stage 1.
// GET  /api/me/keys          → list {provider, key_prefix, created_at, updated_at} (never plaintext)
// PUT  /api/me/keys          → validate + encrypt + upsert {provider, api_key}
// DELETE /api/me/keys?provider=groq → remove
// Gated by BYOK_ENABLED=1 (off → 404, so half-shipped work is invisible).
import { admin, authUser, json } from "../sb.js";
import { BYOK_ENABLED, BYOK_PROVIDERS, encryptKey, keyPrefix, validateKey } from "../keys.js";
import { serve } from "../serve.js";

async function handle(req) {
  if (!BYOK_ENABLED()) return json({ error: "Not enabled" }, 404);
  const user = await authUser(req);
  if (!user) return json({ error: "Not signed in" }, 401);
  const sb = admin();

  if (req.method === "GET") {
    const { data, error } = await sb
      .from("user_api_keys")
      .select("provider,key_prefix,created_at,updated_at")
      .eq("user_id", user.id);
    if (error) return json({ error: error.message }, 500);
    return json({ keys: data || [] });
  }

  if (req.method === "DELETE") {
    let provider = "";
    try {
      provider = new URL(req.url, "https://brandforge.local").searchParams.get("provider") || "";
    } catch {
      provider = String((req.url || "").split("?").pop() || "").replace(/^provider=/, "");
    }
    if (!BYOK_PROVIDERS.includes(provider)) return json({ error: "Invalid provider" }, 400);
    const { error } = await sb.from("user_api_keys").delete().eq("user_id", user.id).eq("provider", provider);
    if (error) return json({ error: error.message }, 500);
    return json({ ok: true });
  }

  if (req.method !== "PUT") return json({ error: "Method not allowed" }, 405);
  const declaredLength = Number(req.headers?.get?.("content-length") || 0);
  if (Number.isFinite(declaredLength) && declaredLength > 16_000) return json({ error: "Request too large" }, 413);
  let body;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid JSON" }, 400);
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return json({ error: "Request body must be an object" }, 400);
  }
  const provider = String(body.provider || "").toLowerCase();
  const apiKey = String(body.api_key || "").trim();
  if (!BYOK_PROVIDERS.includes(provider)) return json({ error: "Invalid provider" }, 400);
  if (apiKey.length < 8 || apiKey.length > 1000 || /[\r\n\0]/.test(apiKey)) return json({ error: "Invalid API key" }, 400);

  const valid = await validateKey(provider, apiKey);
  if (!valid) {
    return json({ error: "This key was rejected by the provider — check it and try again." }, 400);
  }

  let encrypted;
  try {
    encrypted = encryptKey(apiKey);
  } catch (error) {
    return json({ error: "BYOK encryption is not configured on this deployment." }, 503);
  }
  const { error } = await sb.from("user_api_keys").upsert(
    {
      user_id: user.id,
      provider,
      encrypted_key: encrypted,
      key_prefix: keyPrefix(apiKey),
      updated_at: new Date().toISOString(),
    },
    { onConflict: "user_id,provider" }
  );
  if (error) return json({ error: error.message }, 500);
  return json({ ok: true, provider, key_prefix: keyPrefix(apiKey) });
}

// Vercel routing adapter (dual-mode: legacy (req,res) OR Web Request->Response).
const _h = serve(handle);
export default _h;
export const GET = _h;
export const PUT = _h;
export const DELETE = _h;
