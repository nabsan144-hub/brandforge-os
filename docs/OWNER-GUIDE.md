> Current release: read [OWNER-HANDOFF-1.14.md](../OWNER-HANDOFF-1.14.md) first. This reference guide is subordinate to its AI workflow and release boundaries.

# Owner guide — setup, staging, publishing and release checks

This guide is for the owner/operator, not website copy. The code is supplied complete; account-specific secrets, DNS, provider approvals and real-device/payment tests cannot be invented or completed without access. Keep checkout disabled until the evidence below is complete. There is no promise of guaranteed rankings, revenue, security perfection or 100% customer satisfaction.

## 1. Choose the correct artifact and preserve data

- **Source ZIP:** whole supported project: Desktop, dashboard source, operated Cloud, SQL migrations, website, tour/media, tests and operator guides.
- **Owner ZIP:** customer Desktop runtime, compiled dashboard, fonts, license, setup scripts and customer documentation. It intentionally excludes Cloud, website/development files and operator audit notes.
- The old `hosted/` SQLite prototype and Docker/Fly/Railway recipes are retired. Their conflicting lifetime-Cloud/licensing behavior is not part of the product.
- Back up existing files and databases before replacing a deployment. Do not overwrite a customer's data directory with a clean test directory. Run only one Desktop server/process that writes a given data folder at a time.

Desktop Owner remains $199 once, Agency + Source $499 once. Cloud Pro remains $49/month or $490/year; Agency $99/month, Free 3 lifetime campaigns per account. Cloud limits and Desktop license rights remain separate. Confirm capacity, maintenance/support and resale terms before opening sales.

## 2. Run Desktop

Extract the whole archive into a writable folder. Follow `START-HERE.md`: Windows uses `SETUP-WINDOWS.bat` for initial install/repair and `START-HERE.bat` for normal launches. macOS/Linux use the documented Python virtual environment. Initial setup needs internet; normal launch does not run a package manager.

Test the supported OSes with a clean user profile—not just the development environment. Create a brand, upload a logo, generate an offline campaign, edit a text revision, export PDF/DOCX/ZIP, restart and verify persistence. Install the bundled Noto fonts when editing DOCX files. Native Microsoft Word and platform-specific rendering require real-device checks.

The Desktop server is loopback-only. Do not publish it behind a public proxy. Optional Telegram connects to that local server, requires an explicit chat allowlist, and receives messages you send through it. Optional web research and image providers make network requests; the request counter is not a complete packet monitor.

Python wheel builds now include the dashboard and use per-user application data. To build one from Source, first run `npm ci --prefix app/web-modern` and `npm run build --prefix app/web-modern`, then `python -m pip wheel --no-deps ./app`. Use a fresh virtual environment to verify the wheel separately from the source tree.

## 3. Prepare staging services

Create separate **staging** Supabase and Paddle sandbox resources. Use different secrets and domains from production. Configure a commercial-appropriate hosting plan. Do not put real keys into source, screenshots, public JavaScript, an issue or a chat message.

1. Supabase: create the project; obtain URL, publishable/anon key and service-role key from its settings. The anon/publishable key is public; the service role is server-only. The config endpoint rejects recognized privileged keys placed in the public slot.
2. Back up an existing database and verify restoration. Apply migrations in `supabase/migrations/` in filename order through **0015**. For a brand-new project, `cloud/schema.sql` is the generated combined schema. Do not rerun a whole schema over an existing project without a migration plan.
3. Configure Supabase Auth site URL and allowed signup/reset redirects for your staging app. Confirm email verification, password recovery, refresh and logout across tabs. Configure your email sender/domain. If requiring CAPTCHA in Supabase, set the matching public `CAPTCHA_SITE_KEY` in the Cloud deployment.
4. Review deployed grants/RLS using the supplied SQL and the runbook. Service-role RPCs must work; anonymous/authenticated access to private billing, cost and signing tables must fail.

Migration 0011 stores each paid order's release bucket/path/checksum and makes email retries fair with backoff. If you have old **test** orders, clear only disposable test data or reconcile each row to its real original artifact. If real historical orders exist, do not guess their checksum or overwrite their release binding. This project was scoped as prelaunch with no paid legacy promises.

## 4. Deploy the supported Cloud

In Vercel create a project with root directory **`cloud/`**. Configure server environment variables from `cloud/.env.example`; do not paste the example file into public assets.

Required groups:

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
- `BRANDFORGE_APP_URL` and `BRANDFORGE_MARKETING_URL`: exact HTTPS origins.
- An operator Groq and/or Gemini key, and its current input/output USD-per-million-token rates. Blank rates are rejected; do not enter zero unless the service is genuinely free for this account/model. Confirm the model actually used by the code before setting rates.
- `MAX_PROVIDER_DAILY_USD`, `GENERATION_DAILY_BUDGET`, `GENERATION_PAUSED`. Read their semantics in the runbook: conservative reservations are not invoice measurements.
- `RATE_BACKEND=postgres`, or explicitly configured Upstash credentials. There is no fail-open fallback.
- Optional BYOK: `BYOK_ENABLED=1` and a securely backed-up 64-hex-character encryption key. Changing it without migration makes existing saved keys unreadable.
- `CRON_SECRET` (32+ random characters) and the alert webhook. Test the scheduled maintenance job and actual alert reception.
- Keep `CLOUD_CHECKOUT_ENABLED=false`, `DESKTOP_CHECKOUT_ENABLED=false`, `BILLING_RELEASE_VERIFIED=false` while configuring.

Optional WhatsApp is a **private workspace reminder**, not a public client-file share. The recipient must sign in to the owning account. Configure its provider/template/consent settings only if using it. Provider API acceptance does not prove handset delivery.

## 5. Configure Paddle Billing, private releases and email

Use Paddle Billing, not Classic license/file delivery. Create the five distinct USD prices in the launch runbook, with the exact intervals and no unintended trial. Configure sandbox API/client/webhook keys and a strong separate `BILLING_ACTION_SECRET`.

Upload the correct Owner and Source ZIPs to a **private** Supabase Storage bucket. Use versioned object paths and retain old paid artifacts. Set `DESKTOP_STORAGE_BUCKET`, the two release paths and exact SHA-256 values. Do not overwrite one tier with the other or replace an old file without updating/reconciling its integrity metadata.

Set `DESKTOP_DOWNLOAD_SECRET`, `RESEND_API_KEY` and a verified-domain `DELIVERY_FROM_EMAIL`. Create the Paddle webhook for transaction completion, subscription lifecycle and adjustments as detailed in `LAUNCH-RUNBOOK.md`.

For authorized sandbox testing only, enable `BILLING_SANDBOX_TESTING=true` and the relevant checkout flags. Check both guest Desktop purchases, both Cloud intervals, paid-to-paid changes, duplicate clicks, timeouts, portal/cancellation, deletion while billing is unavailable, refunds and disputes. Confirm the actual received email and downloaded ZIP checksum. A 200 response or queued mail record is not inbox proof.

Only after staging passes should you configure matching production keys/prices and perform an **owner-authorized real purchase and refund**. Preserve the real evidence privately. Do not use mocked test records to sign off these checks.

## 6. Publish the website and clean URLs

The site is static, with no third-party runtime CSS/fonts required. In Vercel use root **`sales/`**, build command **`npm run build`**, output **`public/`**. Netlify uses the included config. On Cloudflare Pages use the same command/output; the build copies its headers and redirects. The publish build omits tests, package files and operator-only media notes.

The committed domain is `https://www.brandforge-os.com`. To change the marketing origin use `python scripts/set_site_url.py https://YOUR-ACTUAL-DOMAIN`, then regenerate/check the sitemap. This is configuration, not a reason to edit dozens of pages manually. Set app/marketing URLs consistently in the Cloud environment and Supabase Auth as well.

Normal pages use `/pricing`, `/demo`, `/agents`, `/workspace`, `/docs`, `/tools`, `/privacy`, `/terms`, `/refund` and `/tour`. Old HTML page addresses redirect; query parameters are preserved. Downloadable files retain their genuine extensions. The Google verification file must keep its provider-required name. Unknown pages must return 404, not a successful-looking homepage.

After staging verification, point your registrar's DNS records to the exact values shown by the hosting dashboards. Enable HTTPS and verify the canonical www/non-www choice. Test the real deployed host: redirects, route status, form behavior, video seeking/range requests, captions and sound opt-in. No local preview establishes deployment success.

## 7. SEO and customer acceptance

Confirm unique page titles/descriptions, one meaningful primary heading, internal links, canonical origins, robots and sitemap. Private app/account pages and duplicate tour assets should not be indexed. Submit the sitemap in your verified Search Console account and request indexing only after the live site is correct. Rankings depend on search engines, competition, useful content, links and time—not a code score.

Run manual keyboard/screen-reader and broader-browser checks, especially mobile Safari/Firefox, long brand names, supported languages, forms and exported documents. Ask representative users to create, review, revise and export a real brief; measure confusion, editing time and perceived value. This is how you validate customer satisfaction rather than promise 100% from automated tests.

## 8. Seller/legal and release sign-off

You asked to retain **BrandForge OS** and the existing support email. No legal entity, address or jurisdiction was invented. Verify public seller/support details, privacy/retention, refund/consumer rights, license/resale scope and maintenance commitments with appropriate advice before accepting payment.

Complete a private copy of `RELEASE-VERIFICATION.example.json` for the exact deployed commit. Run the revenue readiness gate with `RELEASE_VERIFICATION_FILE` set to it. All checks must reflect actual evidence. Then deliberately set DESKTOP_CHECKOUT_ENABLED=true and BILLING_RELEASE_VERIFIED=true in the sales build environment, rebuild/redeploy the static site, and set the matching backend production flags. The builder applies the public flag without a source edit. Validate the built artifact with `--sales-public-dir sales/public` (or SALES_PUBLIC_DIR). Until then, the delivered source remains safely payment-gated.

## 9. Operate and recover

Monitor generation errors, reserved provider budget, failed events and pending deliveries. Keep database, private artifact and signing/encryption-key backups. Test restoration. Rotate credentials with an explicit migration/recovery plan; do not invalidate customer links or saved keys accidentally.

During an incident pause generation or checkout, while keeping read/export/portal access available. Never delete uncertain checkout records simply to permit another charge. Preserve the last known-good build and migration history. Run dependency/security checks again at release and periodically afterward.

## Runtime update notes (1.4.2)

- Re-run explicit Desktop setup once to refresh the schema-2 readiness record. Do not attempt to bypass a failed fingerprint with a hand-edited marker.
- Keep the private settings journal with backups and out of logs, tickets and public files. Recovery is for interrupted application writes, not a guarantee against hardware loss or concurrent external editors.
- CLI/Windows browser opening follows server readiness; a foreign listener is not opened as if it were BrandForge.
- The local maintenance scheduler does not invoke an AI engine. History deletion remains opt-in via a positive BRANDFORGE_MEMORY_MAX_ROWS; invalid settings cause no deletion.
- The external account, payment/refund, email, native Windows/macOS/Word and legal checks above remain required. No production flags were enabled by this update.
