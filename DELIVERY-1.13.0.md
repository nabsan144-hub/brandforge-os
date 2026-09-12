# BrandForge OS 1.13.0 — consolidated local delivery

2026-09-12. Complete standalone source, not a cumulative patch. No push, deployment, paid inference, payment activation or signing was performed.

## What was fixed / added
- Shared Cloud/Desktop Canvas: text, shapes and image layers; move/resize/order, duplicate/remove, undo/redo, saved versions and editable JSON/SVG/PNG exports. Server-enforced ownership, revisions, replay protection and attribution. Portable migration is manual JSON transfer, not continuous synchronization.
- Historical artwork without recipes can enter Canvas as a sanitized, flattened reference with new editable layers. Missing semantic text and layout recipes cannot be recovered; no false promise of fully reconstructing old packs.
- Hardened image import rejects active/external SVG content, XML base/escaped resource expressions and oversized data; decode timeout bounds waits. Safe static SVG is flattened. Three-engine malicious-reference tests pass.
- Explicit per-run Desktop no-AI disables text/image/live research without altering saved provider settings. Corrected privacy, draft-check and research labels; provider-connected prompts can leave the PC and incur fees.
- Shared campaign arrival/deadline budget, bounded body reads, cancellation, save reserve and transient-auth 503 behavior. Added real Node entry import after inventory found a duplicate import that Vitest had missed.
- Production Groq default GPT-OSS 120B, production-only Groq fallbacks; explicit account-specific saved models preserved. Public official catalogs checked, not authenticated inference or pricing approval.
- Shared design tokens, root background/color-scheme and WebKit contrast correction; three-browser responsive/theme tests. Standalone owner value dashboard records measured outcomes without inventing customer proof.
- Native packaging and notices expanded. Actual unsigned Linux 1.13 runtime and install/repair/rollback/tamper/failure/uninstall/data-preservation tests pass. Windows/macOS recipes exist but were not executed here.

## Evidence
| Check | Result / boundary |
|---|---|
| Full local release gate | PASS: 450 Python tests (one warning), 438 Cloud tests; build/static/security gates in retained log |
| Actual Node import | Cloud API entry successfully imported, beyond Vitest transformation |
| Chromium / Firefox / WebKit | Each: 56 sales-site views, 21 actual Desktop states, 4 actual Desktop Canvas states, 4 mocked-Cloud Canvas states |
| Canvas importer security | Each engine rejects 9 malicious references; safe SVG flattened; zero external requests |
| PostgreSQL 17 concurrency | 120 campaign requests -> 50 completed; 50 monetary contenders -> 7; 30 checkout contenders -> 1; Canvas 24 replays -> 1 project, 24 competing revisions -> 1 success |
| Local database recovery | Actual dump -> fresh owned database; public/auth table counts and ordered JSONB checksums match |
| Native Linux | Rebuilt 1.13, offline campaign, ZIP/PDF, portable core, Canvas save; actual installer lifecycle passes |

Evidence logs: `docs/audit/final-1.13-evidence/`. All 91 IDs: `docs/audit/91-ITEM-RECONCILIATION.md`. The inventory hashes every included source file and checks supported syntax/credential patterns; it is not a claim that every line was manually reviewed or that no defects remain. Mocked Cloud browser tests are not real Supabase/Vercel journeys. Test router blob interception was corrected in the QA fixtures; real importer security was not weakened.

## Brutally honest product assessment
The Canvas is functional and accessible in the automated sample, but visibly utilitarian: long forms and many explicit controls, not a polished direct-manipulation design suite. The inspected Canvas screenshot is a QA fixture, not an example of customer-quality art. Generated artwork remains a draft requiring copy, crop, rights and full-size review. Passing structural tests does not prove persuasive advertising or fluent multilingual typography.

Free AI and established editors make generic generation alone a weak reason to buy. The credible potential value is a repeatable local workflow, controlled no-AI operation, retained editable source, version history and campaign organization. Whether that saves enough time to justify the price is unproven until real customers measure it. No numerical purchase likelihood, conversion improvement or “professional quality guaranteed” claim is justified by this evidence.

## Still requires the owner — not secretly completed
Real authentication/email delivery and tenant attack testing; actual approved provider calls and model/cost/rights checks; private storage and maximum payloads on the real host; serverless load/tail latency; sandbox billing/webhook replay/refund/fulfillment/deletion; production backup/restore including secrets and storage; remote CI; Windows/macOS execution, signing/notarization and clean machines; dependency/license and legal approval; native distribution approval; fluent-language and assistive-technology review; uncoached usability, comparative/customer pilots and measured value. Team seats/invites are intentionally not supplied; the product is disclosed as single-account.

Do not activate sales or represent these external gates as passed. See `docs/audit/OWNER-HANDOFF.md` for the ordered owner checklist and exact references.
