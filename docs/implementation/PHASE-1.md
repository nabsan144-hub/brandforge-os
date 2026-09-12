# Phase 1 — image-safety implementation

**Status: implemented locally; not deployed; paid-image release gate still CLOSED.**
**Date:** 11 September 2026
**Branch:** `fix/phase-1-image-safety`
**Baseline:** `5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b`

## Completed in this batch

### T01 — explicit image consent and no-AI enforcement

- Cloud imagery is now off unless the operator explicitly sets `AI_VISUALS_ENABLED=true`.
- A paid plan alone no longer starts an image request. The user must check a separate image-sharing control.
- The browser identifies the image provider/model and fields transmitted: product/brand, industry, audience, tone and colors. It states that logos/product photos are not sent and artwork currently applies only to the hero.
- Selecting **No AI providers** disables both text and image generation. The server and engine enforce this even when a caller attempts to submit image consent or accidentally supplies model keys.
- Image consent is cleared when loading/reusing a brief. The browser disables imagery for Free/no-AI/unavailable states.
- New generation requests with absent/stale provider confirmation fail closed. Completed requests still replay after provider configuration changes, avoiding a new idempotency recovery defect.
- Cloud storage is explicitly distinguished from model-provider sharing; no-AI is not marketed as local/offline storage.

### T02 — combined provider cost reservations

- One atomic `reserve_operator_cost` call covers operator text costs plus the operator image upper bound before provider work begins.
- Personal/offline text funding does not bypass image accounting when an image is requested with an AI-capable selection.
- Image estimates are positive, finite and bound to the configured provider/model. Model changes require a deliberate pricing update.
- Missing pricing or budget denial prevents provider calls and releases the still-reserved campaign allowance through the existing failure path.
- Conservative cost reservations are retained after provider failures/uncertain saves. This protects the configured ceiling but is not measured-invoice accounting.
- Existing atomic PostgreSQL budget locking is reused; no second independent image/text reservation race is introduced.

### T04 — saved image state (core complete; recovery remains open)

- Added `supabase/migrations/0012_visual_status.sql` and regenerated `cloud/schema.sql`.
- The migration preserves existing campaigns and marks historical image state as **unknown**, rather than inventing provenance.
- New image states persist in the actual generation RPC and are returned in create/detail/account export. ZIP metadata already retains the campaign fields.
- The detail UI displays image status, provider/model, fallback reason and hero-only scope.
- Existing database ownership restrictions and RPC grants are preserved.
- **Not included:** image-only retry UI or historical status reconstruction. Those remain U03/open work.

### T05 — OpenAI contract

- GPT image requests no longer include unsupported `response_format`.
- Requests specify landscape `1536x1024`, high quality and PNG output rather than square dimensions with a wide-composition prompt.
- The adapter refuses non-GPT-image models rather than pretending one request body works for DALL-E as well.
- Provider/model/key selection is resolved once before accounting/execution. A later environment change cannot silently switch the provider mid-run.
- **Not included:** a real paid provider request. Mock contract tests are not provider certification.

### T06 — export provenance

- Generated guidelines identify the actual image provider, model and timestamp.
- Removed hard-coded Google Gemini attribution and the blanket commercial-use assurance.
- Exports require review of applicable provider/input/likeness/trademark/advertising rights and explain that resized banners remain vector-only.

## Additional defects discovered while implementing

1. **BYOK selector overflow on mobile:** the provider select used intrinsic `width:auto` and overflowed a 390px viewport when visible. Removed that override.
2. **Workspace heading order:** cards jumped from h1 to h3. Changed the section headings to h2 and updated the corresponding layout selector.
3. **Duplicate source tree:** `bfos/` contains another project copy. A root-level Vitest invocation accidentally collected its tests without its separate dependencies. Cloud Vitest now explicitly roots itself at `cloud/`. **The nested copy was not modified or certified.** Confirm its intended purpose before deleting, synchronizing or deploying it; canonical changes in this batch are under root `cloud/`, `supabase/`, `scripts/`, `.github/` and `docs/`.

## Verification performed

| Check | Result |
|---|---|
| Cloud automated suite | **233 passed**, 26 files — 29 more tests than the audited baseline |
| No-AI tests | Free/Pro/Agency at both engine and actual route/database levels |
| Combined budget | Text+image single reservation; image with personal/offline text; invalid costs/model binding; database denial; PGlite ceiling test |
| Actual request lifecycle | Provider cost reservation before fetch; fallback create → detail → account export; duplicate request without another provider call |
| Migration | Existing migration suite passes; image metadata persistence and restricted authenticated RPC grant checked |
| Offline Chromium UI regression | **8 states passed**: Free/Pro × dark/light × 390/1440px |
| UI checks | Consent defaults/reset, no-AI disable, submitted provider/consent, saved fallback display, BYOK view, axe, overflow and page errors |
| Browser result | **0 axe violations, 0 page errors, 0 horizontal overflow** in those eight states |
| Schema synchronization / syntax / diff whitespace | Passed |

The new browser check is added to CI as `image-consent-browser`, with artifact upload on success/failure. It was run locally; no remote GitHub Actions run was triggered. The full sales/Desktop browser harness remains separate work under T11. The original sales light-theme defects have **not** been fixed in this batch.

No production endpoint was modified. No real login, emails, payments, provider charges or database migration were executed. Desktop Python and sales code were not changed; their full suites were not rerun in this batch.

## Reproduce locally

From the canonical repository root:

```sh
npm ci --prefix cloud
npm test --prefix cloud
node cloud/scripts/sync-schema.mjs --check
python -m pip install playwright==1.62.0
python -m playwright install --with-deps chromium
python scripts/image_consent_qa.py
```

The browser harness intercepts all network requests and uses synthetic account/provider/API responses. It does not open a real customer session or contact paid services. Screenshots/results go under `qa-results/image-consent/` by default; set `BRANDFORGE_QA_DIR` to override.

Evidence captured for this batch is in `docs/implementation/evidence/`.

## Staging rollout order — not a production-enable instruction

1. Review this diff against the actual deployed backend revision and confirm the deployment root is canonical `cloud/`, not the nested `bfos/cloud/` copy.
2. Keep `AI_VISUALS_ENABLED=false` and paid checkout gates closed.
3. Take the appropriate database backup and apply **only the new migration** `0012_visual_status.sql` to an existing staging database with migrations 0001–0011 already applied. Do not reset customer tables or replay a fresh-install schema blindly.
4. Deploy the updated API and browser together to staging. Old frontends that omit image consent safely generate vectors.
5. Verify old campaigns still load and report unknown image provenance; verify new statuses and tenant isolation.
6. Before any approved image smoke test, verify current provider pricing and configure its positive conservative bound and exact model binding:

```text
AI_VISUALS_<GEMINI|OPENAI|XAI>_COST_MODEL=<exact configured image model>
AI_VISUALS_<GEMINI|OPENAI|XAI>_MAX_USD_PER_IMAGE=<verified conservative USD upper bound>
MAX_PROVIDER_DAILY_USD=<approved total daily ceiling>
```

These are configuration names/placeholders, not a recommendation to use any particular cost estimate. Include input/output charges for the configured request and review prices when changing models/quality. Never put real provider credentials in public files.

7. **Do not enable paid imagery in production yet.** T03 payload/storage safety is still unresolved. Run any operator-approved provider smoke under a staging spend cap only, then complete T03/V06 and the remaining release gates.
8. Safe immediate rollback is disabling the new image flag and retaining the additive column. Prefer forward fixes. Reverting to the old image code restores the original consent/cost defects and ignores the new kill switch; do not treat that as a safe rollback while image-capable keys remain available.

## Progress and next work

- `MASTER-PLAN.md`: the complete approved implementation plan and original audit.
- `PROGRESS.csv`: all **90 work items**, including unstarted and unverified items. Partial tasks are deliberately not labeled complete.
- Next engineering batch: **T03 payload-safe private assets**, component retry design under U03, and completing image-format disclosure/behavior under T09.
- Then: structured editable fields/free deterministic rerender (T10), output-quality work Q01–Q17, marketing/contrast fixes, and remaining operational launch checks.

This is the first implementation batch, not completion of the entire roadmap or approval to charge customers.
