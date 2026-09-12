> Historical planning document, not a customer promise. The supported 1.4.1 capabilities and release gates are described in docs/PRODUCT-ACCEPTANCE.md, docs/FULL-AUDIT.md and docs/OWNER-GUIDE.md. The old hosted prototype/deployment roadmap is retired.

# BrandForge OS — Roadmap

> **Living docs:** version + product roadmap (this file) · current
> status/releases in [README.md](README.md) + [CHANGELOG.md](CHANGELOG.md) ·
> historical audits in `docs/archive/`.

**North star:** the most trustworthy *one-time-purchase* marketing OS —
vertical depth (marketing, not a generic agent), offline by default,
output you can actually use.

## v1.3 — Desktop (the headline)
- [ ] Full Tauri v2 app: Rust sidecar bundles the Python server;
      `BrandForgeOS.exe` / `.dmg` / `.AppImage`, system tray, auto-update
- [ ] App icons (32/128/512, store sizes), code signing
- [ ] OS keychain for API keys (replaces .env on desktop)
- [ ] "No Python needed" — the real version of the promise we removed in v1.1

## v1.4 — Real images & proof
- [ ] Image generation for banners (local: stable-diffusion via Ollama-compat
      stack or user's API key; never pretend) → replace SVG-only visuals
- [ ] Case-study generator: campaign → before/after scorecard PDF
- [ ] Live in-browser demo on the sales site (hosted sandbox, 1 free campaign)

## v1.5 — Hybrid hosted (shipped scaffold) + agency depth
- [x] Hosted login + Free/Pro/Agency entitlements (`hosted/`)
- [x] Server-side campaign/brand limits + free watermark
- [x] Billing stubs + desktop upsell (hybrid)
- [ ] Paddle subscription webhooks → plan changes (production) — code + tests complete (signed, idempotent, upgrade/downgrade/past_due in `hosted/api/main.py`); remaining: set `PADDLE_WEBHOOK_SECRET` + `PADDLE_PRICE_*` and register the destination in Paddle (see `hosted/deploy/fly-railway.md`)
- [ ] Production origin deploy (Fly/Railway) + app.brandforge-os.com — scaffolding complete (`Dockerfile`, `fly.toml`, `railway.json`, runbook); remaining: operator deploy + DNS + volume
- [ ] Client portal (read-only share link per client, watermarked free tier)
- [ ] Campaign scheduling (publish dates, 30-day calendar → ICS)
- [ ] White-label reports (audit + campaign in client branding, PDF)
- [ ] Paddle webhooks → license issuance, hosted tier, auto-updates

## v1.6 — Intelligence
- [ ] Competitive watch: scheduled re-audits of competitor URLs (daemon),
      diff + change alerts via Telegram
- [ ] Keyword research from live SERPs (Brave/Tavily) feeding keyword_brief
- [ ] A/B copy variants per campaign (3 hooks × scoring)

## Always
- [ ] i18n (Urdu, Hindi, Arabic, Spanish) — beachhead markets first
- [ ] OpenClaw *skill* that installs BrandForge workflows (distribution into
      that community; we compete on done-ness, not architecture)

## Explicit non-goals (for now)
- No CRM/SMS/funnels — that's GoHighLevel's game; we win on
  generation + privacy + one-time price, not client delivery
- No enterprise SSO/SOC2 until we have enterprise demand

---

# Product roadmap (merged from PRODUCT_ROADMAP.md)

## Product decision
BrandForge will launch for **freelancers and small agencies** who create repeat client campaigns. The core promise is: *turn one client brief into an approval-ready campaign pack in a privacy-first workspace.*

## Delivery sequence

### Sprint 1 — conversion and campaign creation foundation (in progress)
- [x] Audit/security/dependency remediation and accessible dashboard build
- [x] Honest local/cloud positioning and corrected marketing sitemap
- [x] Isolated responsive hero animation
- [x] Campaign-template API and dashboard template picker
- [ ] Rewrite all customer-facing sales copy around client-ready outcomes
- [ ] Guided first-campaign onboarding and sample workspace
- [ ] Entitlement matrix for Solo, Agency, Cloud Pro, and Cloud Agency

### Sprint 2 — Brand Brain and campaign quality
- [x] Brand Brain foundation: brand promise, approved proof points, prohibited phrases, and voice context
- [x] Persisted active-client Brand Brain editor with validated server-side updates
- [x] Claim Guard first pass: client-prohibited phrases and generic marketing-risk flags, shown in campaign review
- [x] First Campaign Quality Score: CTA, detail, approved promise/proof coverage, and Claim Guard review signals
- [ ] Extend Claim Guard with unsupported-claim detection and deeper brand-consistency checks
- [ ] Add campaign quality trend/history and reviewer acknowledgements
- [ ] Add approved offers, competitor notes, asset references, and revision history

### Sprint 3 — agency delivery workflow
- [x] Campaign status: Draft, Internal review, Ready for client, Changes requested, Approved, Delivered
- [x] Persisted, validated status-history trail in each campaign record
- [x] Versioned campaign revisions: immutable source campaign, new draft copy, revision lineage
- [x] Client-ready local campaign pack: approval HTML (print-to-PDF ready), copy Markdown, review CSV calendar, creative brief, and ZIP
- [x] Native PDF/DOCX export (reportlab + python-docx; `app/modules/document_exporter.py`, `/api/campaigns/{name}/export.pdf|.docx`)
- [x] Agency white-label export settings: agency identity/footer and configurable BrandForge attribution in approval packs
- [x] Agency logo upload/storage (local: `POST /api/clients/{id}/logo`, PNG/JPEG ≤5 MB, validated with Pillow)
  - [ ] Cloud-hosted logo storage (tenant asset store) — next step

### Sprint 4 — optional hosted collaboration
- [ ] Organization/team roles
- [ ] Revocable, expiring approval links and comments
- [ ] Cloud backups/audit trail
- [ ] Production deployment: Vercel for static sales/front-end; persistent Python host + managed database for hosted API

### Sprint 5 — only after core retention is proven
- [ ] Canva-ready creative brief/export, then optional Canva integration
- [ ] Publishing/export integrations
- [ ] Analytics feedback loop
- [ ] Paddle checkout and webhook activation after live product IDs, domain, tax/refund policy, and email delivery are ready

## Non-negotiable launch checks
- Never label cloud-provider use as offline/private.
- Never activate payment buttons before tested end-to-end delivery and refunds.
- Keep local mode local by default.
- Build client approval and compliance safeguards before autonomous publishing.
