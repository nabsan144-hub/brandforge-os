# BrandForge OS Cloud — Vercel-native (Supabase auth + serverless)

A deliberately scoped browser workspace — Free (3 lifetime campaigns, watermark) / Pro / Agency — rebuilt in the architecture Vercel actually supports (serverless functions + row-level-security Postgres; browser users can read only their own rows while quota-enforced writes stay server-side). Python + SQLite cannot run on Vercel; this can. It is not feature-identical to the desktop/hosted Python product: this port currently produces an SVG campaign hero, does not implement desktop brand profiles or live web search, and exposes WhatsApp delivery only when separately configured.

**Cost: $0** (Vercel Hobby + Supabase Free). Note: Vercel Hobby terms say
non-commercial — for a revenue product upgrade Vercel Pro ($20) when you
start earning, or put this same folder on Cloudflare Pages + Workers later.

## Setup — 15 minutes, clicks only

The static SPA shell is approximately **30.4 KB raw / 9.6 KB gzip** (`cloud/public/index.html`). The Supabase browser SDK is **vendored** at `cloud/public/vendor/supabase.mjs` (a self-contained browser ESM bundle built from `cloud/vendor-entry.js` — see below), so it ships with the site and never depends on a third-party CDN at runtime. Rebuild it with:

```bash
cd cloud && npx esbuild vendor-entry.js --bundle --format=esm --platform=browser --target=es2020 --minify --outfile=public/vendor/supabase.mjs
```

### 1. Supabase (free) — accounts + database
1. supabase.com → New project (free tier).
2. **SQL Editor** → paste the entire `schema.sql` from this folder → Run.
   (Creates profiles/campaigns/usage_monthly tables with row-level security +
   auto-profile on signup — users can only ever read/write their own rows.
   `usage_monthly` + the `reserve_campaign_slot` / `release_campaign_slot`
   RPCs enforce plan quotas **atomically** — if you deployed an older copy of
   this schema, re-run the full `schema.sql`; it is idempotent. BYOK adds the
   `user_api_keys` table — re-run for existing projects too.)
3. **Authentication → Providers → Email** — already enabled by default.
   For instant testing turn OFF "Confirm email"; for production leave it ON.
4. **Settings → API** → copy:
   - `Project URL`            → `SUPABASE_URL`
   - `anon public key`        → `SUPABASE_ANON_KEY`
   - `service_role key` (secret! keep private) → `SUPABASE_SERVICE_ROLE_KEY`

### 2. Vercel — the app
1. Push this `cloud/` folder to a GitHub repo (or upload via Vercel's
   "Add New → Project" with the repo).
2. Vercel → Add New Project → import repo → **Root Directory: `cloud`**.
3. Environment variables (Project Settings → Environment Variables), all
   environments: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
   Optional WhatsApp delivery (Stage 3): `WA_DELIVERY_ENABLED=1`,
   `WHATSAPP_PROVIDER=twilio` (needs `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
   `TWILIO_WHATSAPP_TEMPLATE_SID`, optional `TWILIO_WHATSAPP_FROM`) or
   `WHATSAPP_PROVIDER=360dialog` (needs `WABA_360DIALOG_TOKEN`, `WABA_NAMESPACE`,
   `WABA_TEMPLATE_NAME`, `WABA_TEMPLATE_LANG`), plus `BRANDFORGE_APP_URL`.
   Optional BYOK (bring-your-own-key): `BYOK_ENABLED=1` and
   `BRANDFORGE_ENCRYPTION_KEY=<64-char hex>` (AES-256 key for encrypting
   user API keys at rest). Users can then save their own Groq/Gemini
   key in the workspace; it is validated, encrypted, and never shown again.
   Optional: `GROQ_API_KEY` (free at console.groq.com — switches campaigns from
   the labeled offline engine to GPT-OSS 120B; the three text agents run in
   parallel and provider calls have an eight-second timeout), and the Paddle
   vars below when you take payments.
4. Deploy → your app is live at `https://<name>.vercel.app`:
   - `/` sign in / start free
   - workspace with quota display, campaign runs, per-campaign detail
   - `GET /api/me`, `GET/POST /api/campaigns` (server-enforced limits)

### 3. Paddle (when selling)
- Create Pro/Agency/desktop products; set `PADDLE_CLIENT_TOKEN`, `PADDLE_ENV` (`sandbox` first, then `production`), `PADDLE_PRICE_PRO`, `PADDLE_PRICE_AGENCY`, and `PADDLE_PRICE_DESKTOP_OWNER/AGENCY_SOURCE` (legacy `_SOLO/_AGENCY/_OS` still accepted).
- Webhook → `https://<name>.vercel.app/api/paddle-webhook`,
  set `PADDLE_WEBHOOK_SECRET`. Signature is real HMAC (ts + h1), downgrades
  on cancel, upgrades on activate — same rules as the desktop hosted app.
- In your checkout, send `custom_data: { user_id }` so upgrades land on the
  right account (email fallback exists).

## What is (and isn't) in this port
- ✅ Signup/login/sessions (Supabase, hashed passwords, RLS)
- ✅ Free/Pro/Agency quotas enforced server-side (3 lifetime / 50 mo / unlim)
- ✅ Campaign pipeline: strategy + copy + SEO + hero SVG (offline templates
  labeled honestly; Groq when key set; watermark on Free)
- ✅ Paddle webhook with real signature verification (including desktop-price hosted mirrors)
- ️ Simplified vs desktop: no live web-search step, no landing-page/ICS tools,
  no WebSockets (the SPA doesn't need them). The full 18-tool product remains
  the desktop app / Python hosted app.

## Test checklist after deploy
1. `/` → Start free → account created, workspace opens.
2. Create 3 campaigns → 4th blocked with upgrade message (LIMIT_LIFETIME).
3. Log out / log in → campaigns persist.
4. Without GROQ_API_KEY → badge shows "offline"; with it → "AI".
