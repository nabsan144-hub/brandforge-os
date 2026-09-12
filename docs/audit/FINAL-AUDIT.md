> Current follow-up: see `FOLLOW-UP-1.10.0.md` and the 91-item reconciliation. This earlier report is retained as historical evidence.

> This is the prior 1.9.0 audit. For current changes, test evidence and the repaired history-backup limitation, see `FOLLOW-UP-1.9.1.md`.

# BrandForge OS — final repository-audit handoff

Date: 11 September 2026. Version: 1.9.0. Baseline: `43f87a1`; working branch: `audit/repository-wide-hardening`. The ZIP's generated RELEASE-MANIFEST records the exact packaged commit.

## Bottom line

This handoff contains the complete supported source project, not a patch. It improves tested security, failure recovery, packaging, accessibility, truthful copy and search readiness. **It does not finish all 91 product/business/verification items, establish production readiness, or certify a manual line-by-line review of every file.** Unimplemented work remains explicitly listed in `91-ITEM-RECONCILIATION.md` and `../implementation/PROGRESS.csv`. Those limitations are a shortfall against the requested all-complete scope, not just missing credentials.

I would not open paid acquisition or promise agency-quality, publish-ready output on this evidence. The software provides a review workflow and reusable brand/export conveniences, but the generic vector layouts and remaining short-format omissions do not yet demonstrate a compelling advantage over free AI plus common design tools. Buying likelihood requires real uncoached customer trials at the displayed price, not an assertion from automated tests.

## Scope and method

The initial inventory covered 951 tracked paths and 100,533 text lines, including the conflicting duplicate `bfos/` tree. Every current source path is hash-inventoried and applicable Python/JavaScript/JSON/XML/Bash syntax is checked. Targeted source review and regression tests cover Desktop Python/FastAPI, Svelte/Vite, Cloud JavaScript/serverless/Supabase, SQL, static marketing, CI, packaging and operator documentation. This is not a Next.js project. Binary assets, generated code and historical evidence are retained; inventory does not establish manual review of each line or correctness of each branch.

Current machine-readable inventory is supplied with the handoff. A heuristic credential scan is not a comprehensive secret scanner. Dependency audit outputs describe known advisories at execution time, not a security guarantee.

## Confirmed flaws and exact repairs

| Area / flaw | Repair and principal files |
|---|---|
| Two deployable source trees had drifted | Compared all 424 `bfos/` files: 375 identical, 48 different, 1 unique. Preserved every original byte with a manifest in `RETIRED-bfos-DO-NOT-DEPLOY.zip`; removed the active duplicate. Do not deploy the historical ZIP. |
| Tracked runtime data blocked the actual release | Real package build rejected six tracked state files: active client, non-default client, SQLite database and three memory documents. Preserved them separately as private historical state and removed them from source; the default Studio template remains. No runtime data belongs in a customer release. |
| Source restoration and stale release manifest could misrepresent provenance | Restored prior Phase 6A-equivalent baseline using 137 hashes; packager requires clean committed source, excludes the old manifest, creates exactly one self-excluding per-file hash manifest and checks it. `app/make_release_zip.py`, `RELEASE-MANIFEST.json`. |
| Packager required ignored build output instead of shipped dashboard | Requires tracked packaged dashboard and verifies its referenced assets. Regression: `app/tests/test_repository_audit.py`. |
| Windows quality gate could fail to resolve npm.cmd | Resolves executable with `shutil.which` before subprocess launch. `scripts/check_release_quality.py`. Native Windows execution still requires a real machine. |
| Supabase SDK calls lacked bounded abort-aware fetch; Node 20 realtime constructor compatibility | Added 12-second request deadline with caller abort support and explicit `ws` transport. `cloud/api/_lib/sb.js`, package lock. |
| Paid-mail draining could spend excessive time in serial retries | New bounded queue: maximum 20 selected orders, two workers, 600 ms start pacing, 15-second attempts, 30-second batch budget, backlog/deferral metrics. `delivery-queue.js`, `fulfillment.js`, `routes/maintenance.js`; real SQL with mocked transport tests. Does not prove whole-maintenance wall time or live throughput. |
| Public configuration risk from unapproved credential fields | Restricts credential-related public configuration to the intended allowlist. `cloud/api/_lib/routes/config.js`. |
| Failed private download left poor recovery | Safe retry action retains the fragment-derived capability in memory; `cloud/public/desktop-download.{html,js}`. No token-in-URL-query workaround. |
| Plain comparison prose was damaged by HTML sanitization | Corrected text handling in `app/modules/security.py`; regression retained. |
| Desktop startup could leave a blank/unhelpful screen | 10-second session handshake timeout, token validation, failed-start instructions and Reload action; same-origin capability handling retained. `app/web-modern/src/main.js`, `app.css`. |
| Mobile Desktop navigation visibly overlapped despite no document overflow | Wrapped navigation/status groups, responsive network panel, disclosure aria state and nav geometry assertion. `App.svelte`, `app.css`, actual-ASGI browser harness. |
| Desktop heading hierarchy, logo input label and theme contrast | Root sections use h2, Settings subsections h3, logo upload has an accessible name; light gold/emerald/amber palette corrected. Dark selected-brand contrast addressed; reduced-motion CSS prevents unwanted transitions. Generated dashboard rebuilt. |
| Misleading provider/value wording | Settings distinguishes text and image entitlement, optional connected imagery and local file security. Offline text selection does not promise no network if an image provider is explicitly selected. Extra-size copy corrected to 21. No provider access or output superiority implied merely by entering a key. |
| Marketing and setup claims were inconsistent | Narrowed absolute language, output and ownership claims, removed unsupported founder specifics, corrected install command, kept Cloud/Desktop distinction and conservative availability. Removed decorative orb-interaction instructions. `sales/index.html`, `pricing.html`, `docs.html`. |
| Search/indexing and static publishing gaps | Clean-route handling, noindex/private-app robots, canonical/link/asset/heading/metadata checks across 14 pages, 13-URL sitemap, intrinsic image dimensions. `sales/*`, `cloud/vercel.json`, `cloud/public/robots.txt`. No invented `/services` or `/logo` product pages; examples were treated as URL-format requirements. Real files keep extensions. |
| Pricing FAQ structured data could drift from visible answers | Semantic FAQ synchronizer and checks, with refreshed structured data. `scripts/sync_pricing_faq_jsonld.py`. |
| Operator docs overstated or lagged current state | Migration instructions now through 0015; daily 03:00 UTC cron distinguished from the monitored five-minute paid-delivery requirement. Older audits labeled historical. New acceptance guide acknowledges optional AI hero and limited corrections. |
| Browser coverage missed actual Desktop application | Added in-process real FastAPI + built Svelte Chromium bridge, 20 states; source-site 56-view CSP/axe/overflow gate; CI wiring and evidence. These are not deployed/native certification. |

The source commit diff is the exact file-level change record. Historical Phase 1–6A fixes and evidence remain under `docs/implementation/`; they are not all newly introduced by this audit.

## Executed checks

| Check | Observed result |
|---|---|
| Final sequential release gate | PASS: Python, Ruff, Cloud, Sales tests/build, Desktop build, schema sync, prelaunch configuration |
| Python | 419 passed, 1 Pillow test deprecation warning; final gate 147.53 seconds |
| Production Python statement coverage (separate measured run) | 4,934 / 6,145 statements = **80.29%**. Branch coverage not measured. |
| Cloud | 368 passed / 35 files |
| Sales | Funnel 37, demo 54, accessibility 14 checks; CSS/contrast/integrity gates passed; 14 pages checked |
| Source-site Chromium | 56 views: 14 pages × two themes × 390/1440 widths; no reported axe violations, document overflow or page errors under shipped CSP |
| Actual Desktop Chromium | 20 states: four initial, 12 additional tabs, four failed-session/reload recovery combinations; no reported failures |
| Specialized browser checks | Consent, watermark exports, private assets, visual review, vector corrections, Editorial quality, Editorial workspace and availability scripts passed |
| Wheel build | 1.9.0 built; isolated clean-install/native OS acceptance not established |
| Known dependency advisories | Cloud, Sales, Dashboard npm audits: zero; requirements pip-audit: no reported vulnerabilities |
| Prelaunch | PASS, explicitly **not revenue-ready** |

One earlier full Cloud run overlapped browser activity and suffered a worker exit at 365/368. The isolated rerun passed 368/368, as did the final sequential release gate. The original failure output was overwritten; the precise cause is unproven. No OOM diagnosis is claimed.

Visual inspection of the actual light mobile Desktop caught navigation overlap that automated overflow checks missed. It is now corrected and geometry-tested. Selected marketing and Desktop screenshots were inspected; not every page/state/output was manually assessed. Transition-induced contrast findings prompted legitimate reduced-motion support, not disabled axe rules.

## Preserved contracts

- Free generated-image attribution remains enforced; paid newly generated assets differ as already documented. Logos and historical saved exports are not rewritten.
- No Free AI trial, new provider activation, paid call, push, deployment or payment activation was performed.
- Editorial remains explicit opt-in, Bold the default; 20 legacy golden renders remain unchanged.
- Corrections remain default-off and limited to supported inline canonical vector recipes. Private, AI and legacy assets are not falsely presented as fully synchronized.
- Thirty Editorial fixture renders are not thirty publishable designs: ten report omissions; five ordinary strips omit fields and five long stress cases are rejected/nearly blank. Native Urdu/Hindi advertising review remains outstanding.

## Remaining work — not concealed as complete

All 91 IDs are preserved. Open work includes distinct composition families, client-specific creative direction, approved product imagery, improved showcases/story outputs, language review, targeted image retries, broader edit/sync workflows, team/client/portability features, nontechnical native packaging, instrumentation, support policy and customer pilots. Many are substantive development/design tasks, not settings the owner can simply toggle.

Live gates remain: auth/email/CAPTCHA; deployed tenant isolation; no-AI network observation; model entitlement/current prices/real outputs; maximum high-entropy assets through Vercel/storage; concurrent budgets; deletion/retention; payment/webhook/refund/inbox delivery; monitored backlog recovery; native OS/Word/browser/assistive-technology matrix; backup restoration; legal and seller approval. No ranking, revenue, zero-bug or 100% satisfaction guarantee is supportable.

Read `OWNER-HANDOFF.md` next, together with the full existing `../OWNER-GUIDE.md` and `../LAUNCH-RUNBOOK.md`. Archive verification/checksums are delivered separately to avoid a self-referential ZIP checksum.
