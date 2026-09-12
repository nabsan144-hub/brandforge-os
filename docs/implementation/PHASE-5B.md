# Phase 5B — Saved, no-charge vector corrections

**Implemented and tested locally. Not pushed, deployed or enabled.**

Branch: `fix/phase-5b-vector-corrections`. Runtime gate: `VECTOR_CORRECTIONS_ENABLED=false` by default.

## Supported scope — read this first

This batch supports **newly generated inline vector campaigns with a saved rendering recipe**. It does not rebuild historical campaigns by guessing their inputs. It refuses to replace AI-scene campaigns or private-bundle campaigns. Vector fallbacks with a valid new recipe are eligible, but no image provider is retried.

T10 is still **partial**. This is a working correction/versioning path for that supported subset, not universal copy/visual synchronization. Private-bundle replacement, AI-scene reuse and migration of legacy rendering inputs remain open.

## What users can do

- Edit the saved **headline, subheadline, short offer/price/terms text, CTA and destination**.
- Save corrected vector banners without a text/image provider call or another campaign allowance charge.
- Review the resulting format report, preview the images, and acknowledge the exact version before campaign export.
- Restore an earlier managed version's **exact stored visual bytes and matching text snapshot**, without re-rendering those old bytes through a potentially newer renderer.

The destination is HTTPS-validated **export metadata**, not a printed URL or clickable ad destination configured with an advertising platform. Offer/price/terms are a single short free-text field, not a currency/terms engine.

### What is deliberately unchanged

Original product/brand, logo files, logo concepts, benefits, colors, style choice, dimensions and watermark policy remain fixed. The form explicitly displays the existing benefits as unchanged. Some layout variation is derived from text, so changing a headline can reflow the composition within the same style.

**Free-form strategy, copy and SEO are not automatically rewritten.** Correcting an offer does not search-and-replace old prices in those documents or the unchanged benefit text. Users must review all occurrences. This limitation is shown in the editor, review notice and ZIP field metadata.

Free attribution is frozen from the original server-created recipe, not accepted from correction requests. A client cannot change the watermark, dimensions, colors or recipe through this endpoint. Existing paid outputs do not gain a watermark merely because the account plan later changes; original Free outputs do not lose theirs after an upgrade.

## Persistence, restore and safe failure

Migration **0015_vector_corrections.sql**, after 0014:

- Adds canonical visual fields and a bounded rendering recipe to newly completed campaigns. AI-scene recipes are intentionally absent.
- Adds service-role-only `campaign_visual_versions` rows containing immutable inline file sets, fields, recipe and format report.
- Before the first correction, stores the original file set and links prior text snapshots to it. It then saves the new files and advances the campaign revision in one transaction.
- Retains the current file set plus those referenced by the last ten saved text revisions. Unreferenced visual versions are pruned after corrections, text edits and restores. Campaign/account deletion cascades the version rows.
- Restores managed visual/text snapshots together, but always invalidates review acknowledgment. Existing unversioned text-only restore retains its conservative previous behavior.
- Uses owner checks, row locking, expected revisions and request IDs. A committed request replay does not create another revision. Reusing its ID for different fields fails. Replay never overwrites later edits/restores.
- A failed/oversized save leaves existing files/history untouched and does not consume campaign allowance. A missing expected revision cannot authorize an update.

The frontend retains the request ID while retrying the same correction after an uncertain response. It distinguishes a completed old request from a newer current version. Older review-only clients must reload before reading, acknowledging or restoring managed visual sets.

### No paid model call is not zero infrastructure cost

The correction endpoint performs deterministic rendering and database writes. Normal hosting, CPU and storage costs still apply. It has a per-account safety limit of **60 correction attempts per hour**; it does not reserve or increment the campaign ledger.

Inline payload and response caps remain in force. Each stored version payload is capped at 3MB. The current campaign also retains its current files for compatibility, so history deliberately duplicates some data. Up to eleven distinct retained file sets plus the current campaign can approach roughly 36MB of file payload per campaign, before other metadata. This is a staged implementation, not the final private-storage architecture.

## Fit reporting and exports

The renderer reports whether each requested field is present, omitted, or needs a fit check for each format. Small strips intentionally omit the headline/offer; the UI now names those omissions rather than implying a successful field update is visible everywhere.

**“Included” is not a legibility, contrast, proofing, platform-compliance or correct-price certificate.** The report inspects outlined-text metadata; it can conservatively flag repeated text and does not replace inspecting the images.

- ZIPs include `VISUAL-FIELDS.json` with the canonical inputs, per-format report and limitations, plus the existing review notice and SHA-256 manifest.
- Account export includes retained visual versions as a separate paged dataset, so historical file bytes are not silently omitted.
- The existing compressed response cap still applies to combined archive pages. If an unusually large page exceeds it, the endpoint fails explicitly; support recovery remains necessary. Live maximum-size archive/restore proof is still a release gate.
- Operator inline recovery now includes both text snapshots and retained visual versions. Recovery files remain exclusive-create and mode 0600 on supported POSIX systems.
- The legacy private-conversion CLI and its SQL attachment function refuse managed vector-history campaigns. Converting just their current files would orphan the intended history semantics. That storage migration requires separate implementation.

## Verification

| Check | Result |
|---|---|
| Full Cloud suite | **318 tests across 32 files passed** |
| New vector-correction suite | **22 tests passed**, using actual rendering and real PGlite migrations/RPCs |
| New Chromium correction flows | **4 views passed**: dark/light × 390/1440px |
| Existing review/archive flows | **4 views passed again** |
| Existing consent/accessibility | **8 states passed again** |
| Existing watermark exports | **18 PNG/JPEG checks + ZIP hashes passed again** |
| Existing private-bundle exports | **10 PNG/JPEG checks + ZIP and portable JSON passed again** |
| Syntax, schema sync, whitespace | Passed |

New tests cover server-generated recipes, no provider calls, quota preservation, immutable attribution, unchanged non-banner files, restricted inputs, unsupported campaign refusal, old clients, optimistic revision conflicts, uncertain-save replay, later-edit preservation, exact restore, retention, deletion, archive pagination, role grants, rollout gating and pre-save payload rejection.

The new browser harness uses **the actual engine and correction renderer** to prepare its fixtures, then runs the shipped UI under its CSP with offline API responses. It verifies field submission, same-ID retry after a simulated lost committed response, omission reporting, review before download, ZIP contents/hashes, original-copy preservation, watermark pixels and restoration of original fields/files. Zero axe violations, horizontal overflow or page errors across its four views.

SQL behavior and browser behavior are tested separately; this is not an end-to-end live Supabase deployment proof. The new browser gate is added to CI, but **remote CI has not been run here**. The previous review harness's dialog synchronization was made deterministic after a timing race under the newly restored Chromium environment; assertions were not suppressed.

Evidence is under `docs/implementation/evidence/phase-5b-*`. The sample PNG demonstrates working corrections and attribution, not a creative-quality overhaul.

## Staging rollout

1. Back up staging. Apply 0015 **after 0014** using the migration workflow. Deploy matching API, config, UI, export tools and operator scripts in a coordinated maintenance window; the new archive/recovery code requires the new table even while corrections are disabled.
2. Keep `VECTOR_CORRECTIONS_ENABLED=false` initially. Existing version-aware reads/restore must remain available regardless of this flag.
3. Enable the flag only in staging and create a fresh **inline, vector** campaign. Historical campaigns do not receive retroactive recipes. Private-bundle campaigns are not eligible; enabling private storage for all new campaigns does not make these correction features available to them.
4. Test owner isolation, stale tabs, unknown/missing recipes, image/private refusal, nonce reuse, lost responses, concurrent edits, restore, archive pages, retention and deletion with the actual services.
5. Test real maximum-size supported packs and mobile memory/latency. Review storage growth, the existing 60-second function budget and cleanup behavior. End-to-end deadline/observability work remains open.
6. Verify no model, payment, generation quota or asset-storage mutation occurs during corrections. Only the intended inline campaign/version data should change.
7. Verify signed/portable exports, exact old-version bytes and operator recovery against a real staging backup. Do not infer production recovery readiness from fixtures.
8. Record evidence before enabling production. All payment, image and private-storage gates remain separate; none was changed here.

### Rollback

Set `VECTOR_CORRECTIONS_ENABLED=false` to stop new corrections. **Keep** migration 0015, the version-aware reader/exporter, restore functions and retained history. Completed-request replay remains available. Do not drop the table, strip version pointers, bulk-mark campaigns approved, or convert only the current files to private storage. Prior Phase 3/5A rollback restrictions still apply.

## Workspace recovery note

This turn's restored checkout was at Phase 4 with the delivered Phase 5A files uncommitted; its recorded Phase 5A commit object was not retained. The workspace was compared against the previously delivered Phase 5A ZIP manifest. All delivered files matched except the CI workflow, which was restored from that archive. The exact delivered Phase 5A changes were preserved in recovery commit `d097462` before starting this branch. No unrelated user edits were overwritten. The original reported Phase 5A commit hash and the recovery hash differ; the phase-only patch is content-compatible with the delivered Phase 5A files.

## Remaining plan

T10 remains partial for private/AI/history migration, separate benefit/price/terms handling, and synchronization of free-form copy. T03's live storage/maximum-output gates, creative-quality improvements, billing/Desktop operations, release evidence and other open work remain tracked. The complete **91-item tracker** is preserved. The duplicate `bfos/` source remains untouched.

**No production migration, deployment, paid-provider request, key change or payment activation was performed.**
