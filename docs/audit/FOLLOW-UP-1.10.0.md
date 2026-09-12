# 1.10.0 implementation and audit record

Date: 2026-09-11. Baseline: `bc445164603193ec10ffc910d24b83ddecacc211` (delivered 1.9.1). The release ZIP's manifest supplies the exact new commit and file hashes.

**Complete source delivery is not backlog completion or production approval.** All 91 original IDs remain. Nineteen still say Not started; many others remain partial or externally unverified. The operating playbook and proposed business decisions are not substitutes for implementation, real users, legal review or paid-service evidence.

## Confirmed gaps/fixes in this batch

| Gap / defect | Exact change and scope |
|---|---|
| No customer-supplied product photography workflow | Cloud upload, explicit rights, browser header/pixel/byte bounds, JPEG preparation, server normalization/metadata stripping before quota reservation. Reject remote URLs, malformed images, missing permission and mixed uploaded/AI imagery. Photos are never included in model requests. |
| Insufficient distinct compositions | Opt-in product-v1, offer-v1, service-v1 and evidence-v1. Distinct photo, offer, benefit and supplied-proof layouts; customer palette, contrasting ink, contained photo edges, story margins and explicit whole-field omissions. Legacy defaults and saved renderer compatibility retained. |
| Cannot inspect the actual brief without saving/using allowance | Authenticated `/api/campaign-preview`, forced offline, no keys/ledger/campaign mutation, plan-aware, rate limited, deletion guard. UI format selection and fit warnings before Create. Connected generation may change text; preview is not a promise of identical AI output. |
| Preview could remain visible after brief changes or race a changed brief | Input changes invalidate/revoke prior previews; completed stale responses do not appear as the current brief. Product browser test covers both an existing preview and edits during an in-flight preview. Photo-load request generations guard competing uploads; brand load invalidates a pending photo. |
| JPEG source download reported the wrong MIME | `.jpg`/`.jpeg` source downloads now use `image/jpeg`. Source bytes and ZIP hashes verified. |
| Paid navigation still said Upgrade | Cloud button now says Plans & billing; it does not imply enabled checkout or a needed upgrade. |
| No safe operational overview separate from mutating maintenance | Read-only `/api/ops-status`, timing-safe CRON_SECRET auth, shared 10-second SDK signal, parallel aggregates, no customer notes/content. Unauthorized/method/read-only regression tests. |
| Maintenance had independent timeouts but no shared abort | Shared 50-second signal through SDK, delivery worker transport and alert fetch. Two workers retain 15-second per-attempt and pacing limits. Abort regression verifies already-allocated workers receive cancellation and remaining work is deferred. This does not preempt synchronous CPU or prove deployed p95/p99. |
| Support intake risks requesting excessive customer information | Tested Desktop installation-only diagnostics and internal triage/escalation/privacy checklist. Mailbox operation and staffing must be assigned/verified by owner. |
| Business cost discussion lacked a executable scenario tool | Validated Decimal-based calculator with refund, usage, fee, hosting, support, acquisition and maintenance reserve inputs. Seven tests cover math, invalid values and zero outputs. Example figures are explicitly hypothetical. |
| Release labels drifted during development | 1.10.0 pyproject, changelog and checkout manifest synchronized; consistency regression and full release gate pass after correction. |

## Decisions made without inventing permissions

- New composition families are Cloud-only and opt-in; Bold remains default. There is no automatic layout recommendation or default rollout based on fabricated customer preference.
- Product photos are campaign-specific, not reusable brand moodboards. Browser PNG transparency flattens to white; output is resized JPEG, not lossless original preservation. Plan limits apply; at most three chosen photo formats plus hero.
- Product-first requires a photograph, Offer-first an offer and Evidence-first supplied proof. Supplying proof is not verification that the proof is true. Important terms are never partially printed to fit; a whole field may be omitted with warnings. An omitted price is still a reason to reject or revise an ad.
- Preview is template-only, even if the form requests a connected provider. It must not consume a lifetime campaign or silently call an image model.
- No new schema migration, payment enablement, provider key acquisition, secret changes, deployment, remote Git push, signing identity or paid external calls.
- Solo marketers serving service/retail businesses are the working segment hypothesis. Human pilots, economics and legal acceptance are mandatory before claiming a demonstrated advantage.

## Local evidence

Sanitized logs are under `docs/audit/product-workflow-evidence/`. Test artifacts are reproducible with the scripts; the release excludes generated QA scratch.

- Full local release gate: **428 Python tests**, **394 Cloud tests / 39 files**, Ruff, Sales tests/build, Desktop Svelte/Vite build, schema sync and prelaunch config pass. One existing Pillow deprecation warning remains; it is not a failing behavior.
- Product-specific API/engine/PGlite tests: 11 pass. Real migrations and renderer; hosted auth/storage remain mocked.
- Product browser: 8 Free/Pro × light/dark × 390/1440 states, rights rejection, no-save previews, stale-preview rejection, exactly one Create, source imagery, ZIP SHA-256s, attribution, no axe violations/page errors/external requests/overflow. The photograph is a synthetic corner-marker fixture, **not a real product-quality benchmark**.
- Other rerun browser gates: Sales 56 views; actual local Desktop 20 states; consent 8; practice 8 plus four tampered-data rejections; availability 8; correction 4; visual review 4; editorial workspace 4; watermark 18 raster checks; private-asset export passes. Editorial corpus: 30 renders, 10 explicitly reporting omissions. No claim of universal visual quality.
- Dependency audits: Cloud production dependencies, Sales and Dashboard report zero known npm advisories; pip-audit of app requirements reports no known vulnerabilities. This is time-specific, not proof of exploit-free dependencies.
- Whole-tree inventory/syntax/credential-pattern scan passes. This inventory includes untouched files but is **not a new line-by-line expert manual review of every file**, complete branch coverage or a penetration test. Earlier audit records remain historical evidence, not newly executed proof.

## Honest output and purchase assessment

The new families and actual product photo make the workflow more useful than repeating one generic layout, particularly when product fidelity matters. The inspected mobile fixture preserves the corner markers and surfaces omissions. That is correctness evidence, not evidence that an ad looks professionally art-directed.

I would not recommend buying from this synthetic sample alone, or claim BrandForge now beats free AI/design alternatives. Generic vector work, deliberate omitted fields, limited editing and unproven real-device/customer journeys still weaken the offer. The plausible value is a repeatable, reviewable branded pack with predictable exports—not superior imagery, replacement of a designer/agency or guaranteed time savings. Compare real briefs, end-to-end effort and willingness to publish before paying for growth.

## Remaining implementation (not just owner configuration)

Examples of still-unimplemented scope: image-only provider recovery/stage progress; universal copy-to-visual editing; crop/replacement/logo placement controls; scoped Cloud client review/comments/approval; permission-tested team seats if later chosen; versioned Desktop/Cloud transfer; signed/native packaged installation; consolidated cross-app design tokens; full privacy-conscious funnel and usable-export dashboard; automatic composition selection and client-specific brand/moodboard systems. The original Karak, fitness, skincare, property and legacy public showcase rebuilds still need work. Do not advertise these as delivered.

External gates also remain: real CAPTCHA/auth/email, deployed tenant isolation and payloads, authorized provider/payment/refund/inbox/storage/outage checks, monitored scheduler/alerts, restores, Windows/macOS/Word/Firefox/Safari/assistive-technology tests, fluent Urdu/Hindi advertising review, real customer pilots, seller/license/privacy review and invoice-based economics. Exact owner procedures are in `OWNER-HANDOFF.md` and `docs/operations/OWNER-OPERATIONS.md`.

No certification of 100% correctness, satisfaction, rankings, revenue, live readiness or all-backlog completion is made.
