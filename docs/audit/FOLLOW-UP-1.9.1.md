# BrandForge 1.9.1 — fresh follow-up findings and remaining work

11 September 2026. Started from the exact delivered 1.9.0 ZIP, commit `d7ba4d2946079f4c248cc5b22dde54058e0ab4bd`. Every source hash matched the restored checkout. No production configuration or prior audit assertion was treated as live-service proof.

## Honest scope result

**The request to complete everything is still not fulfilled.** This follow-up implements additional work and fixes newly reproduced defects; it is not an all-91-items completion or manual every-line certification. The current tracker preserves 91 IDs, including 35 marked Not started and other partial/unverified items. Some are substantive development/design tasks, not merely owner configuration. See `91-ITEM-RECONCILIATION.md` and `../implementation/MASTER-PLAN.md` for the original acceptance criteria.

The delivered archive is the whole source tree, not a patch or an installer with bundled dependencies. This does not imply that every proposed future feature is implemented. No guarantee of zero defects, universal customer satisfaction, ranking, profitability or production readiness is justified.

## Confirmed findings and exact repairs

| Finding | Change / evidence |
|---|---|
| Provider-image validation checked MIME/base64/bytes but did not fully decode the raster; useful large scenes were rejected before compression | Added `cloud/api/_lib/scene-image.js`. Only PNG/JPEG/WebP signatures and decoders are accepted; corrupt data, vector/PDF formats, multiple pages, excessive source bytes and pixel bombs fail closed. Auto-orients, strips metadata, scales inside 1536×1536 without cropping/enlargement, flattens transparency on white and emits JPEG quality 82, max 1.5 MB. Input max 6 MB / 16 million pixels; response reader remains bounded at 8.1 MB. Nine tests include a real high-entropy PNG above the former output limit. |
| Native decoding could burden ordinary text/vector cold starts | Lazy-load Sharp only after basic validation; limit its cache and per-image concurrency. Native pipeline has a five-second processing timeout. This is not an end-to-end request deadline or deployed latency certification. |
| Dependency candidate had known advisories | Rejected Sharp 0.34.5 after npm audit reported high-severity inherited vulnerabilities; final lockfile pins 0.35.4 and npm audit reports zero known advisories. The vulnerable candidate is not in the committed release. |
| No no-allowance practice flow | Added standalone clean `/practice`, independent of auth/config APIs. Two fictional Northline offer packs are pre-rendered through the real offline Cloud engine. Visitors can compare offers, inspect all SVGs and download source/PNG/copy/metadata/checksummed ZIPs without consuming an account campaign. `scripts/build_practice_sample.mjs` forbids model requests while rendering. This is clearly a static demonstration, not live generation or proof that all asset types support corrections. |
| Practice failure/revision handling needed integrity and stale-state protection | Manifest SHA-256 and byte counts checked before enabling preview/export; eight-second fetch timeouts; generation counter ignores stale loads; old previews/copy are cleared during replacement; export locks version selection; blob URLs released. Four tampered-sample cases rejected by real browser tests. |
| Allowance information was scattered and incomplete at the action | New `allowance.js` derives summary from actual account limits/usage, subtracts in-progress reservations and never shows negative availability. Create explains saved fallbacks, unsaved failures, edit/export/correction usage, deletion, UTC daily/monthly resets and non-resetting Free lifetime usage. Three unit tests; existing server reservations unchanged. |
| Returning from billing could show a clickable stale campaign-review button while its backing campaign was null | Reproduced twice in the actual browser review journey. Hide detail controls synchronously when leaving billing and while loading a campaign; set aria-busy; reveal only loaded detail. Regression deliberately delays detail GET and verifies cancel/accept acknowledgment plus ZIP hashes. No review bypass added. |
| Hero kept animating off screen and did not react to changed motion preferences | IntersectionObserver pauses off-screen animation; reduced-motion change events and page visibility govern resume. Dedicated motion lifecycle regression checks static mode, off-screen, hidden-tab and preference changes. |
| Mobile hero had three competing large actions and too much implementation text before proof | Kept one primary CTA plus a quieter sample action, reduced mobile top padding, moved the tour link down and put workflow details in a disclosure after the product screenshot. Image-treatment caveats remain beside the image showcase. Source-site checks cover 56 theme/width/page views. |
| Positioning and product claims still overstated capabilities | Desktop says Local Campaign Workspace rather than Marketing Department. Pricing no longer guarantees connected models improve quality or that every Cloud campaign has a quality score. Explicit single-account scope excludes team seats, client portal and automatic Desktop/Cloud sync. Cloud is not called an identical Desktop review flow. Visible FAQ and structured data remain synchronized. |
| Prior Git-history backup was not independently cloneable | Previous bundle verification checked metadata against an existing shallow checkout, not a clean clone. Missing parents caused restoration failure. Recovered its packed objects, fetched the missing public upstream ancestry read-only, and passed git fsck. The new backup must be independently cloned and checked before replacing the old backup during final cleanup. The previously delivered source ZIP was intact throughout. |
| Test execution failed under resource pressure | Two full Cloud attempts lost workers. This time kernel logs explicitly record OOM kills; `/tmp` contained 608 MB on tmpfs, including 256 MB of old pytest output. Removed obsolete pytest scratch, retained logs, reran all 380 tests successfully. Release gate already uses disposable disk-backed scratch. No assertion was disabled to obtain a pass. |
| Version metadata drift during development | Version-consistency regression caught the 1.9.1 pyproject with a 1.9.0 changelog. Added the matching changelog and updated the source notice; targeted version regression passed. |

## Verification actually executed

- Full sequential release gate passed after corrections: **419 Python tests** (one Pillow test deprecation warning), Ruff, **380 Cloud tests / 37 files**, Sales tests and publishing build, Svelte/Desktop build, schema synchronization, prelaunch validation.
- Source Sales browser: **56 views**, no reported axe violations, document overflow or page errors under shipped CSP.
- Actual FastAPI/Svelte Desktop browser: **20 states**, passing.
- New practice browser: **8 views**, all preview and ZIP hashes checked, **4 corrupted-sample rejections**, **zero API/provider requests**. This is distinct from static asset requests needed to load the page.
- Consent: 8 states; watermark: 18 raster checks; private-assets exports; corrections: 4 states; visual review: 4 states; Editorial: 30 renders, 10 with omissions; Editorial workspace: 4 states; availability: 8 views/8 states — passed locally.
- New scene normalization: 9 tests; allowance: 3 tests; hero-motion lifecycle regression passed.
- Inventory and syntax scan covers every current nonignored source path. It is mechanical coverage, not evidence of reading/testing every line. Final inventory is supplied separately so it can include the handoff documentation without recursive hashing.
- Selected practice and mobile marketing screenshots were visually inspected. Not every output or screenshot was manually assessed.
- The prior measured **80.29% Python production statement coverage** is historical evidence, not a newly measured complete-code coverage claim. Branch coverage remains unmeasured.

Raw success and failed-attempt records are retained under `follow-up-evidence/`. Final ZIP checksum, packaged commit and independent restore verification are supplied outside the ZIP to avoid self-referential checksums.

## Decisions and preserved behavior

1. Normalize generated *scene photography* to bounded JPEG rather than trying to preserve every original provider byte. This intentionally removes metadata and may alter photographic fidelity/transparency; it does not modify customer logos or old saved exports. Actual paid outputs need visual acceptance before enabling the provider.
2. Practice is pre-rendered and unauthenticated, not a free-provider loophole or a hidden campaign creation route. Its three selected formats demonstrate layouts, not Free-plan entitlement. All practice visuals retain attribution.
3. Existing Bold/default rendering, explicit Editorial opt-in, saved renderer compatibility, no-AI rules, paid/Free attribution and default-off limited corrections remain intact. No private/AI/legacy correction support is implied.
4. Team seats/client portal/sync are explicitly excluded, not secretly implemented or marked complete. Existing HTML page redirects remain configured; `/practice` is clean and noindex. Downloadable file extensions stay intact.
5. No push, deployment, paid call, payment activation or invented owner/service credentials. Fetching public Git history was read-only.

## Still not complete

The remaining implementation includes product/reference imagery, multiple distinct creative families, stronger client-specific art direction, showcase revisions, broader image/copy correction and image-only retry, live job progress, client approvals, portability, installer improvements, metrics and operating workflows. Human language/customer benchmarks, unit economics and seller/legal decisions remain unproven.

The old Editorial deficiencies were not erased: 30 renders still include ten omission cases; five ordinary strip cases omit fields and five long stress cases are rejected/nearly blank. The new practice page is not proof this quality backlog is solved. I would not present these results as a demonstrated agency-quality advantage over free AI/design alternatives or begin broad paid acquisition on this evidence.

Live auth/email/CAPTCHA, deployed tenant isolation, real model contracts/costs, maximum asset delivery, concurrent budgets, payment/webhook/refund/inbox delivery, deletion/retention, monitored backlog recovery, backup restoration, native Windows/macOS/Word/browser/assistive-technology checks and legal approval remain release gates. The owner guide provides configuration and evidence steps; unbuilt features still require development, not just those steps.

Use `OWNER-HANDOFF.md` for exact installation, staging, provider/native-dependency checks and Windows CMD GitHub commands beginning with your requested folder. Use the tracker rather than assuming a whole-source ZIP means the entire proposed product backlog is finished.
