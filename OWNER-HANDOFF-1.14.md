# BrandForge OS 1.14 — owner handoff

**12 September 2026 · Complete source release · Checkout remains OFF**

Read this first. It supersedes earlier owner checklists for the revised AI-campaign workflow. `DELIVERY-1.14.0.md` lists the verified scope; `docs/audit/FINAL-AUDIT-1.14.md` records findings and evidence. No account, deployment, paid generation or checkout was activated during preparation.

## 1. What you have

The standalone source ZIP includes Desktop/FastAPI, the rebuilt Svelte dashboard and packaged dashboard assets, Cloud/Vercel API and browser application, all 25 SQL migrations, shared Canvas, the website and its media, tests, packaging scripts, licenses and documentation. It is not a patch requiring previous ZIPs. Dependencies are declared, not bundled as `node_modules` or a Python environment. Initial source setup needs internet.

AI mode generates **three separately composed advertisements**: hero 1200×630, square 1080×1080 and story 1080×1920. The current adapters are Gemini, OpenAI and xAI—not arbitrary endpoints or every AI service. Gemini/OpenAI support consented product/approved-logo references; xAI references are explicitly rejected. Adding another provider requires an adapter and tests, not merely entering an arbitrary URL.

Each AI format has a portable Canvas JSON and SVG. PNG export is supported. Existing AI lettering/product imagery is a raster layer; it is **not reconstructed editable type**. Canvas supports adding/replacing editable text/shapes/images, saves, revisions and export. Provider aspect ratios can produce padding; bounded web images are not 4K/print masters. Review spelling, product likeness, offers, claims and safe areas. No automatic quality score certifies those things.

Basic layouts remain available deliberately, including additional preset/custom sizes and geometric logo concepts. Those are not silently substituted when a three-format AI campaign fails. AI mode does not accept extra sizes or a request for separate logo concepts. Desktop’s HTML landing page remains a basic page layout, not an AI-designed website.

## 2. Preserve your current installation

1. Back up the whole existing PC project, its real `.git`, `.env`, private configuration, customer folders and databases **outside** the replacement folder.
2. Verify the ZIP against its adjacent SHA-256 file. Extract it into a new folder; do not run inside the ZIP. The archive has a `brandforge-os/` top-level directory.
3. Do not copy private/customer data into the Git repository. Do not overwrite an unknown dirty checkout. Keep the backup until install, data and Git checks pass.
4. The workspace historical archive preserves prior unique material and genuine Git objects. It is not needed to install the new source. `scripts/restore_workspace_history.py` restores selected historical entries to a NEW folder; never deploy a historical tree accidentally.

## 3. Run Desktop manually

Install Python 3.10+; the verified Linux environment used Python 3.13. Windows: run `SETUP-WINDOWS.bat`, then `START-HERE.bat`. Initial dependency setup needs internet. Normal launch does not install packages. See `START-HERE.md` for macOS/Linux source setup.

For development, install a supported current Node release (Node 22 is a sensible baseline), then:

```cmd
cd /d "D:\My creations\AI agent\Brandforge os\BrandForgeOS"
npm ci --prefix app\web-modern
npm run build --prefix app\web-modern
```

Use Settings to select an image provider and enter its own key. Explicit image-provider selection can run images even when text is offline. Auto uses one keyed provider only when the campaign is connected. **The per-campaign no-AI checkbox disables text, images and live search.** Reference sharing starts unchecked. Three generation requests may incur provider fees, including unsuccessful attempts; use your provider account’s spending controls as well.

Smoke test with a non-sensitive client: save a brand/logo, generate no-AI, edit a section, open Canvas, save/reload/restore, export ZIP/PDF/DOCX, restart and confirm persistence. A Windows/macOS signed installer still needs a build, signature and clean-device lifecycle test on that OS. A Linux build is not certification of Windows/macOS behavior.

## 4. GitHub: existing clone or fresh clone

Use `PUSH-WINDOWS-CMD.txt`. It contains exact commands for your folder, repository and email. Review the staged diff; push a **new branch**, not a force-push to main. A push can trigger repository-connected deployment integrations: create staging projects/disable unintended production auto-deployment before pushing if necessary.

If your folder already has a genuine `.git`, preserve it. If it does not, clone the real remote into a fresh empty folder first, then apply the extracted release contents while preserving the clone’s `.git`. Do not use a blind `git init` to invent unrelated ancestry. Review deletions as well as additions; a simple file overlay can leave obsolete tracked files. The ZIP manifest is the authoritative file list. Historical Git can alternatively be restored from `git/final-1.14.bundle` in the history archive.

## 5. Create isolated staging — no purchases needed for this step

You perform these account operations. Do not use production customer data.

1. Create a separate Supabase staging project under your account, if your available plan permits it. Create two disposable test users. Configure Auth email confirmation/reset redirects for the staging app origin, not production. Verify email delivery; default service limits are not a production SMTP guarantee.
2. Create two Vercel projects from the GitHub repository: one with root **`cloud`**, another with root **`sales`**. Use a staging branch/domain for each. Sales build: `npm run build`, output `public`. Keep secrets in the Cloud project only.
3. Record the exact assigned HTTPS origins, e.g. `https://YOUR-CLOUD-STAGING.vercel.app` and `https://YOUR-SALES-STAGING.vercel.app`. These examples are placeholders, not provisioned projects.
4. In Cloud, set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `BRANDFORGE_APP_URL` and `BRANDFORGE_MARKETING_URL`. The service-role key must never go in browser JS. Copy the remaining required names from `cloud/.env.example`, leaving paid features disabled.
5. In Sales, set the **same public** `BRANDFORGE_APP_URL` and `BRANDFORGE_MARKETING_URL`. The build rewrites published first-party links and SEO metadata. Vercel Preview builds publish `robots.txt` with `Disallow: /`. For a staging project deployed as Vercel “Production,” add deployment protection/noindex yourself; do not assume the Preview flag applies.
6. Start with `CLOUD_CHECKOUT_ENABLED=false`, `DESKTOP_CHECKOUT_ENABLED=false`, `BILLING_RELEASE_VERIFIED=false`, `AI_VISUALS_ENABLED=false`, `AI_CAMPAIGN_ENABLED=false`. No provider keys are necessary for no-AI checks. Do not enable payment sandbox code against live payment credentials.
7. Apply migrations **0001 through 0025 in order** to a fresh staging database. Existing databases apply only unapplied migrations, after backup. `cloud/schema.sql` is generated and is for fresh/manual setup, not an upgrade over populated data.

With the Supabase CLI installed/authenticated locally, an example migration sequence is:

```cmd
cd /d "D:\My creations\AI agent\Brandforge os\BrandForgeOS"
supabase login
supabase link --project-ref YOUR_STAGING_PROJECT_REF
supabase db push --dry-run
supabase db push
```

Confirm the linked project before the final command. Enter passwords/tokens locally, never into chat or Git. If using SQL Editor instead, execute the numbered migrations once in ascending order and maintain the migration record; do not replay initialization scripts on existing tables.

### Staging acceptance checklist

- Signup, verification, reset, logout, invalid/expired sessions and two-account isolation.
- Cross-account campaign, private asset, Canvas, review link, export and deletion attempts must fail appropriately.
- No-AI generation, progress, reload, history, duplicate brief, revisions, ZIP/PDF/PNG and portable Canvas transfer.
- Slow/failed requests, exact-request retry, conflicting saves and simultaneous allowance/cost reservations. Check History before generating another chargeable request.
- `/api/capabilities`, public availability text, clean `/pricing`, `/demo`, `/tour`, `/signup` paths, canonical links, mobile menus, keyboard operation, theme and reduced-motion behavior.
- Back up database AND objects/configuration, restore into another isolated project, and compare content/access. The local 29-table database restore does not prove external object/email/payment restoration.
- Keep a redacted record of commit/deployment, timestamp, expected/actual result and evidence. A healthy endpoint is not full acceptance.

## 6. Enable and evaluate paid AI only when funded

Do **not** enable this now merely because the code exists. No live paid-model output was generated or aesthetically approved through the application during this release.

1. Choose one provider and a model you can access. Defaults currently are Gemini `gemini-3-pro-image`, OpenAI `gpt-image-2.5-sunburst`, xAI `grok-imagine-image-2.0`. Catalog presence does not establish account access, unchanged API behavior or the best result for your niche.
2. Configure the matching image key and optional `AI_VISUAL_MODEL`. Set that provider’s `AI_VISUALS_<PROVIDER>_COST_MODEL` to the **exact model ID** and `AI_VISUALS_<PROVIDER>_MAX_USD_PER_IMAGE` to a verified conservative all-in upper estimate, including inputs/other billable components. Provider names for Cloud cost variables are `GEMINI`, `OPENAI`, `XAI`.
3. Set an affordable `MAX_PROVIDER_DAILY_USD` and low `GENERATION_DAILY_BUDGET`, plus provider-account caps/alerts. The application reserves **3 × the per-image upper estimate**, plus any operator-paid text estimate. This reservation is not the provider invoice; uncertain/failed attempts do not refund the global cost reservation.
4. Enable both `AI_VISUALS_ENABLED=true` and `AI_CAMPAIGN_ENABLED=true` in staging only. Use a paid-plan staging test account under your control; do not bypass customer entitlements in public code.
For the paid-plan staging account in step 4, use only the staging Supabase SQL Editor as its owner:

```sql
-- STAGING ONLY: replace this with your own disposable test account.
update public.profiles
set plan = 'pro', plan_status = 'active'
where id = (select id from auth.users where email = 'YOUR-STAGING-TEST-EMAIL');
```

Confirm exactly one intended row changed. Never grant public/customer entitlements this way in production.

5. Generate actual campaigns using approved product assets: all three formats, each intended language and each provider/model you will sell. Compare at full size against the approved Crunch direction and your real commercial reference. Check brand/product identity, exact offer and spelling, hierarchy, margins, CTA safe areas, compression and consistency—not just “a file was returned.” Obtain native-language review where needed.
6. Test invalid key, quota/rate limits, partial provider failure, timeout, retry, changed provider/model consent, references, download and actual billing. Record invoice cost and latency. Do not publish the fictional concept gallery as proof these application runs passed.
7. If outputs fail this quality bar, keep paid launch closed and revise the prompts/adapter or model choice. API mocks cannot replace this gate. Evaluate unit economics against the advertised plan allowances before enabling sales.

Current official model documentation: https://ai.google.dev/gemini-api/docs/image-generation and https://developers.openai.com/api/docs/guides/image-generation . Recheck pricing and commercial/privacy terms for your account when enabling a model.

## 7. Payments, delivery and production

Follow `docs/LAUNCH-RUNBOOK.md` and `docs/RIGHTS-MATRIX.md`. Test Paddle sandbox checkout, duplicate/out-of-order webhooks, subscription changes, cancellation/refund/failed payment, Desktop order fulfillment and account deletion. Bind release artifacts to hashes in private storage; verify download expiration/ownership and email delivery. Never publish a service key or signing key.

**Scheduling:** the supplied daily 03:00 UTC Vercel cron does not meet a five-minute paid-delivery target. Before sales, configure a supported monitored five-minute schedule or authenticated external scheduler calling `/api/maintenance` with the required secret. Verify actual execution and alerts. Do not assume a free hosting plan supports commercial operation or that cadence.

Approve seller identity/tax, privacy/retention, licenses/trademark checks, refund/support terms, staff coverage and recovery procedures. Build/sign/notarize Windows/macOS on their actual platforms and test install/update/repair/rollback/uninstall with standard users and retained customer data. Only then deliberately enable checkout and production AI, deploy the accepted commit and recheck live URLs.

## 8. Explicit boundaries—not hidden unfinished implementations

This release does not promise arbitrary AI-service compatibility, automatic semantic reconstruction of raster lettering, general vector-path editing, team seats/invites, continuous Cloud/Desktop synchronization, guaranteed product fidelity, print-ready masters, guaranteed sales/SEO rankings, or certified signed installers for untested operating systems. These are not silently described as existing features. Actual account, paid-output, legal and device acceptance remains necessary; no 100% correctness or satisfaction certificate is asserted.
