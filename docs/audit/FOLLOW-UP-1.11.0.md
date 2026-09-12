# 1.11.0 — implemented workflows and remaining acceptance gates

Date: 11 September 2026. Source candidate, not production approval. This report supersedes the current-status statements in 1.10.0 reports; historical evidence is retained. All 91 original IDs remain in `../implementation/PROGRESS.csv` and `91-ITEM-RECONCILIATION.md`.

## Exact changes and observed defects fixed

| Finding / gap | Implementation | Evidence |
|---|---|---|
| No Cloud client review workflow | Default-off owner-issued, revision-bound expiring fragment capability; hashed token, revoke/edit/delete invalidation; unverified reviewer names and bounded responses; private download lifetime bounded | Migration 0016, `campaign-review.js`, client-review tests, eight review/archive browser views |
| No Desktop/Cloud archive transport | Schema-v1, checked bytes and SHA-256, safe leaf names, opaque downloads, owner-scoped bounded storage. Explicit core fallback includes text and hero and lists omitted files | Migration 0017; transfers route; Python/JS validators; 10 Python portable tests, browser QA |
| Normal Desktop packs exceed portable capacity | Full transfer refuses rather than truncates; owner can explicitly choose partial core export. Original ZIP remains authoritative | Actual native failure reproduced, fixed workflow and native core smoke passed |
| Failed image fallback required whole campaign regeneration | Default-off paid-account recovery, consent, current revision/idempotency, lease, three attempts/account/day and independent operator budget; original remains on failure | Migrations 0018/0021; image-recovery tests; private recovery/restore test. Provider mocked, no paid calls |
| Private vector packs could not be corrected/restored | Verify immutable original bundle and every file manifest, stage immutable replacement, atomically attach, retain referenced visual history, queue only unreferenced bundles for cleanup | Migrations 0020–0022; six private-version tests including corrupt bytes, restore, pruning and replay |
| Benefits/proof, product image and layout correction gaps | No-provider redraw supports benefits/proof, existing-logo left/right/hide where supported, supplied product-photo replacement and contain/center crop in Product-first. Rights required; attribution/dimensions/style protected | Layout allowlist and payload guards, actual renderer tests and correction retry/export/restore browser QA |
| Uniform manual composition selection | Explicit `auto-v1` chooses Product/Evidence/Offer/Service/Editorial; saved legacy styles remain unchanged | Product workflow tests; sample generator |
| Unreproducible showcase and misleading purchase boundaries | Fictional reproducible gallery with supplied drawn photo references; prices/source-buyer duties and Cloud/Desktop decision path clarified; no paid model calls or fake customer results | Reviewed gallery manifest, Sales integrity/browser checks |
| Signup challenge configuration could fail open | Public CAPTCHA key validation and optional required/fail-closed mode; actual Supabase enforcement is an owner configuration | Signup protection tests; no live signup claimed |
| No optional funnel observations; incorrect success placement/race | Default-off explicit opt-in, strict no-content event schema, daily HMAC pseudonym, daily dedupe, 30-day retention and protected aggregates. Save/paid-plan observations occur after confirmed server state. Revocation aborts pending traffic; stale failure cannot overwrite a new consent session | Migration 0019; five metrics tests; ops-status tests |
| Inconsistent semantic state styling | Shared JSON tokens, reproducible CSS copies, focus/error/success/spacing/type variables linked across three surfaces; release drift check | Token check, Desktop and Sales browser QA. Legacy styling is not fully migrated |
| No package-manager-free startup candidate | Current-OS PyInstaller runtime with bundled dashboard/fonts, per-user state and loopback launcher; manual Windows/macOS build-and-smoke workflow | Linux 1.11.0 native start/dashboard/offline generation/ZIP/PDF/core portable smoke passed |

## Honest boundaries / ambiguity decisions

- Portable means **content archive**, not editable project migration or automatic sync. Full JSON limit is 3 MB; private native bundles may reach 20 MB and therefore cannot always be transferred whole. Partial exports are explicitly labeled and require an owner choice. Imported artifacts never execute automatically.
- A client link is a bearer capability, not a verified identity, legally authenticated signature, team seat or organization permission system. Anyone receiving it can forward it. Public deployment remains gated.
- Corrections support saved recipe-backed vectors, including private storage. Existing AI artwork and recipe-less historical packs are not silently redrawn. Free-form copy remains separately editable and must be reviewed against corrected visual fields. Layout family/dimensions are not a universal canvas editor; new source logo replacement and arbitrary image panning are not provided by this correction form.
- Image recovery covers a supported vector fallback hero only. Resized vectors, logos and copy remain unchanged. It is not unlimited free provider use, multi-scene recovery or real-provider proof.
- Native build is unsigned and current-OS only. Linux smoke is not Windows/macOS certification. The source release includes build recipes, **not** a customer-approved native binary or installer. Complete dependency-license notices, signing, OS dialogs, uninstall/update and clean-device support need owner/platform verification before native redistribution.
- Metrics are client-reported observations: not verified payments, unique humans, attribution, revenue or usable-output proof. Consent revocation cannot retract a request already received by the server; retention remains disclosed. Do not use events as accounting data.
- UI token consolidation is a foundation; a complete legacy styling migration and manual assistive-technology/native-language review remain open.
- No credential, paid provider, deploy, GitHub push, purchase activation, live customer test or legal approval was performed.

## Local evidence

Full Python suite: 438 passed. Final combined release gate: Cloud 423 passed across 45 files; Python 438 passed (one Pillow test deprecation warning); Ruff, Sales tests/build, dashboard build, schema, token drift and prelaunch configuration passed. The earlier changelog heading/version mismatch was caught by the release test and fixed before the final passing run. Product browser: 8 views; correction browser: 4 views; review/archive browser: 8 views; Desktop browser: 20 states; Sales browser: 56 views. Browser auth/storage/provider services are mocked; actual local renderers and Desktop runtime are exercised where described. Logs are in `remaining-workflows-evidence/`.

## What remains beyond code above

Use the 91-row reconciliation, not a feature count, for acceptance. Remaining work includes universal/legacy/AI editing and editable cross-product migration; full legacy UI consolidation; genuinely customer-validated brand/design output; supported native installers; real staging auth/tenant/storage/payment/email/provider/deletion/backup tests; legal/seller policy approval; support staffing and funded maintenance; uncoached paid-value and pricing pilots. These are not marked complete. This release substantially implements missing workflows but does **not** finish the entire original backlog.
