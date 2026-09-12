// BYOK helpers: validate provider keys and encrypt them at rest.
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { CLOUD_TEXT_MODEL } from "./engine.js";

export const BYOK_PROVIDERS = ["groq", "gemini"];
export const BYOK_ENABLED = () => process.env.BYOK_ENABLED === "1";

function cryptoKey() {
  const value = process.env.BRANDFORGE_ENCRYPTION_KEY || "";
  if (!/^[0-9a-fA-F]{64}$/.test(value)) {
    throw new Error("BRANDFORGE_ENCRYPTION_KEY must be 32 bytes of hex (64 chars)");
  }
  return Buffer.from(value, "hex");
}

export function encryptKey(plain) {
  const value = String(plain || "");
  if (!value || value.length > 1000 || /[\r\n\0]/.test(value)) throw new Error("Invalid key value");
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", cryptoKey(), iv);
  const encrypted = Buffer.concat([cipher.update(value, "utf8"), cipher.final()]);
  return `${iv.toString("hex")}:${cipher.getAuthTag().toString("hex")}:${encrypted.toString("hex")}`;
}

export function decryptKey(payload) {
  const parts = String(payload || "").split(":");
  if (parts.length !== 3 || !/^[0-9a-f]{24}$/i.test(parts[0]) || !/^[0-9a-f]{32}$/i.test(parts[1]) || !/^[0-9a-f]+$/i.test(parts[2])) {
    throw new Error("Malformed encrypted key payload");
  }
  const decipher = createDecipheriv("aes-256-gcm", cryptoKey(), Buffer.from(parts[0], "hex"));
  decipher.setAuthTag(Buffer.from(parts[1], "hex"));
  return Buffer.concat([decipher.update(Buffer.from(parts[2], "hex")), decipher.final()]).toString("utf8");
}

export function keyPrefix(apiKey) {
  return String(apiKey || "").slice(0, 8) + "…";
}

async function fetchWithTimeout(url, options, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export async function validateKey(provider, apiKey) {
  const key = String(apiKey || "").trim();
  if (!BYOK_PROVIDERS.includes(provider) || key.length < 8 || key.length > 1000 || /[\r\n\0]/.test(key)) return false;
  try {
    if (provider === "groq") {
      const response = await fetchWithTimeout("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: process.env.CLOUD_TEXT_MODEL || CLOUD_TEXT_MODEL,
          max_tokens: 1,
          messages: [{ role: "user", content: "ping" }],
        }),
      });
      return response.ok;
    }
    const response = await fetchWithTimeout(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-goog-api-key": key },
        body: JSON.stringify({ contents: [{ parts: [{ text: "ping" }] }], generationConfig: { maxOutputTokens: 1 } }),
      }
    );
    return response.ok;
  } catch {
    return false;
  }
}

// Compatibility helpers must preserve the same fail-closed semantics as the
// campaign resolver. Never silently bill the operator after a corrupt BYOK row.
export async function resolveGroqKey(sb, userId) {
  return (await resolveCampaignKeys(sb,userId,'groq',{allowMissing:true})).groqKey;
}
export async function resolveGeminiKey(sb, userId) {
  return (await resolveCampaignKeys(sb,userId,'gemini',{allowMissing:true})).geminiKey;
}

// Resolve the selected provider explicitly. A personal key ALWAYS outranks
// an operator key in auto mode; decryption/storage errors fail closed rather
// than silently sending the brief to a different provider.
export async function resolveCampaignKeys(sb, userId, requested = 'auto', {allowMissing=false} = {}) {
  if (!['auto','offline','groq','gemini'].includes(requested)) throw new Error('Unknown provider');
  if (requested === 'offline') return {groqKey:'',geminiKey:'',key_source:'offline'};
  const personal = {};
  const result = await sb.from('user_api_keys').select('provider,encrypted_key').eq('user_id',userId);
  if (result.error) throw new Error('Could not read personal provider settings');
  for (const row of result.data || []) if (['groq','gemini'].includes(row.provider) && (requested==='auto'||requested===row.provider)) {
    if (!BYOK_ENABLED()) throw new Error('Personal key encryption is unavailable; no provider was selected');
    personal[row.provider] = decryptKey(row.encrypted_key);
  }
  const selected = requested !== 'auto' ? requested : personal.groq ? 'groq' : personal.gemini ? 'gemini' : process.env.GROQ_API_KEY ? 'groq' : process.env.GEMINI_API_KEY ? 'gemini' : 'offline';
  const key = personal[selected] || process.env[selected === 'groq' ? 'GROQ_API_KEY' : 'GEMINI_API_KEY'] || '';
  if (selected !== 'offline' && !key && !allowMissing) throw new Error('The selected provider has no configured key');
  return {groqKey:selected==='groq'?key:'',geminiKey:selected==='gemini'?key:'',key_source:personal[selected]?'personal':selected==='offline'?'offline':'operator'};
}
