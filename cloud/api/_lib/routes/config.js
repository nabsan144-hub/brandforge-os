// Public client config (anon key is safe to expose by design; RLS protects data).
// Domain-agnostic: marketingUrl and appUrl come from env vars, not hardcoded.
// If not set, frontend falls back to relative or current origin.
import {WA_ENABLED,providerConfig} from "../deliver.js";
import { AD_SIZES } from "../engine.js";
import { serve } from "../serve.js";

async function handle() {
  const publicKey=String(process.env.SUPABASE_ANON_KEY||'').trim();
  let privileged=publicKey.startsWith('sb_secret_') || (!!publicKey && publicKey===process.env.SUPABASE_SERVICE_ROLE_KEY);
  if(publicKey.split('.').length===3){
    try{const claims=JSON.parse(Buffer.from(publicKey.split('.')[1],'base64url').toString('utf8'));privileged ||= claims.role!=='anon';}catch{}
  }
  if(privileged)return new Response(JSON.stringify({error:'Workspace configuration is unavailable.'}),{status:503,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});

  return new Response(JSON.stringify({
    supabaseUrl: process.env.SUPABASE_URL || "",
    supabaseAnonKey: publicKey,
    // Domain-agnostic URLs — set in Vercel env vars to your actual domains (any domain)
    marketingUrl: (process.env.BRANDFORGE_MARKETING_URL || process.env.BRANDFORGE_APP_URL || "https://brandforge-os.com").replace(/\/+$/, ""),
    appUrl: (process.env.BRANDFORGE_APP_URL || "").replace(/\/+$/, ""),
    // Optional Cloudflare Turnstile site key. Empty => the SPA shows no
    // CAPTCHA (current behaviour); set CAPTCHA_SITE_KEY (and the matching
    // provider secret in Supabase Auth) to enforce a challenge on signup/login.
    captchaSiteKey: process.env.CAPTCHA_SITE_KEY || "",
    // Banner preset catalog for the workspace form (public, non-secret data —
    // the same list the pricing page advertises).
    adSizes: AD_SIZES,
    whatsappEnabled: WA_ENABLED() && !!providerConfig((process.env.WHATSAPP_PROVIDER || "").toLowerCase()),
  }), { headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

// Vercel routing adapter (dual-mode: legacy (req,res) OR Web Request->Response).
const _h = serve(handle);
export default _h;
export const GET = _h;
