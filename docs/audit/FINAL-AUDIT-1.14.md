# Fresh repository audit — 1.14

12 September 2026. This audit covers the current repository, not just the changed files. The per-file inventory hashes every included file and applies applicable syntax checks. That inventory is **not** a claim that every line received manual review or that no undiscovered defect can exist. Targeted code review, complete automated suites, real browser flows, native execution and PostgreSQL checks provide the additional evidence below.

## Scope and method

- Python/FastAPI, native lifecycle, local security, campaign orchestration, references, exports, storage and settings.
- Node/Vercel Cloud routes, authentication/ownership, consent, generation, reservation/idempotency, private assets, revisions, Canvas, payment/delivery gates and public capabilities.
- SQL migrations and actual concurrent transactions/restore, not only mocked SQL calls.
- Svelte source **and rebuilt shipped dashboard**; shared JS Canvas; website HTML/CSS/JS, links, themes, effects, keyboard interactions, accessibility and clean-URL deployment rules.
- Dependency manifests/locks, packaging/build scripts, CI/deployment configuration, licenses, customer copy and owner documentation. This repository has no Next.js application; its web applications use static JS and Svelte with Node/FastAPI backends.
- Binary media/fonts were inventoried and exercised through their consumers. Images are not source-code syntax checks; licensing/signing and real-device acceptance remain separate.

## Findings fixed in this release

| Finding | Fix / verification |
|---|---|
| The new homepage accidentally lost its orb canvas | Restored the actual DOM canvas and correct layering; DOM regression plus real motion, click-handler and reduced-motion checks in Chromium/Firefox/WebKit. |
| Weak old artwork was presented as the main design showcase | Replaced the main showcase with the approved fictional Crunch direction, clearly labeled as separately generated concepts. Genuine workspace demonstration remains distinct. Public provenance no longer contains internal owner-review notes. |
| Image workflow did not create complete AI advertisements in all formats | Added gated Cloud and keyed Desktop three-format full-ad generation. Basic variants are not returned as a successful AI campaign after failure. |
| Implicit provider/model/public-image fallback could violate selection | One selected/keyed adapter/model per execution; unsupported selections/capabilities fail. No cross-provider/model retry. |
| References were absent from the new workflow | Added explicit consent, supported-provider transport and real image decoding before external calls. Gemini inline images and OpenAI multipart edits are separately tested. xAI references fail before calls. |
| Old product-photo validation blocked AI references | AI-campaign path now accepts consented prepared photos without requiring the basic Product-first layout. |
| Three images could be priced as one | Model-bound reservation multiplies the upper per-image estimate by three, combined with operator text costs. Failed/uncertain global reservations remain conservative. |
| Provider/model could change after the consent screen | Provider/model confirmation checks and execution snapshots; refresh/review required for a mismatched supplied model. |
| Desktop imported a nonexistent Canvas validator | Corrected to the actual canonical validator; generated sources validate and open through the real native application. |
| Desktop Canvas button ignored portable AI source | It now loads `canvas_hero.json` first and falls back to historical SVG only when that file is absent. Raster-lettering boundary is explicit. |
| Additional sizes/logo requests could be silently ignored in AI mode | Clear preflight rejection and disabled incompatible Cloud controls. Basic mode retains those capabilities. |
| Native parallel generation/error behavior was incomplete | Bounded three-worker execution, explicit preflight/provider errors and no silent basic substitution. Desktop and Cloud surfaces explain retry/cost boundaries. |
| Saved approved logo and AI export descriptions could be misleading | Preserve the approved logo separately; replace obsolete AI branding guidance; distinguish basic landing HTML from AI advertisements and bounded web output from print masters. |
| Local request bodies lacked a general bound | Four-MB declared/streamed body cap, with regression tests before endpoint completion. |
| Desktop white-label checkbox used the retired `show_vanguard_branding` field | Corrected to `show_brandforge_branding`; actual browser save/readback confirms false persists through the real API. This was found outside the originally changed generation path. |
| Expanded Settings success feedback failed light-theme contrast | Replaced dark translucent feedback backgrounds with theme-safe card surfaces and status/alert roles. Expanded Settings now passes browser accessibility checks. |
| Opt-in local maintenance only started through `python server.py` | Moved startup/shutdown into ASGI lifespan so native/uvicorn entry points behave consistently; lifecycle regression added. |
| Staging links/SEO were tied to production origins | Build-time HTTPS-origin overrides for Sales; Preview robots exclusion; invalid origin inputs rejected. |
| Runbook stopped at migration 0015 | Corrected through 0025; fresh versus existing database instructions distinguished. |
| Public imagery availability only understood hero-only mode | Capability/readout now recognizes configured three-format campaigns while retaining truthful legacy status. |
| Dependency-reuse symlinks could bypass directory-only ignore/package rules | Ignore environment names as files or directories, reject included filesystem symlinks, and test environment-link exclusions. The final ZIP is independently checked for both forbidden names and symlink entries. |
| Inventory could report zero files when extracted inside an ignored parent Git repository | Require the Git top-level to equal the inspected source root; otherwise scan the actual files. A real nested-repository regression proves this edge case. The final independent check is outside the preparation repository. |
| Source checkout manifest still carried the previous version | Updated the source notice and used the canonical packager, which excludes that notice before writing one exact schema-2 artifact manifest. |
| Older browser wrapper claimed an engine selection it ignored | Wrapper now actually selects the requested browser. WebKit inline/blob export interception was fixed in the test harness, not misclassified as a product raster-export failure. |

## Executed evidence

Evidence is in `final-1.14-evidence/`; the release manifest identifies the exact packaged files.

- **463 Python tests passed**, with Ruff clean and native Cloud route import successful.
- **464 Cloud tests passed across 50 files**, including 11 new AI-campaign execution/reference/cost/consent tests. All image API responses were mocked; they prove implementation behavior, not art quality.
- Complete Sales tests, accessibility/CSS checks, Sales build, Svelte production build, canonical Canvas/token synchronization, schema synchronization and prelaunch-safe configuration checks passed.
- Three browser engines: repository website **56 views each**, actual Desktop **21 states each**, Canvas **4 views each**, and broad website/Cloud wrapper **98 views each**, with no reported accessibility violations/overflow/page errors in those probes.
- Showcase **12 states / 48 full-size previews**, plus normal-motion, real hero click and reduced-motion assertions for each engine.
- Separate consent/browser checks for the new campaign mode, legacy image consent, private assets, product workspace, revision/restore, review/transfer, Canvas security and watermarked exports passed.
- Actual PostgreSQL 17: 120 competing campaign attempts, exactly 50 completions, no deletion refunds; 50 cost attempts/7 accepted reservations; 30 checkout attempts/1 accepted checkout. Canvas replay/conflict/role tests passed. A dump/restore matched **29 tables** exactly at the logical row level.
- Unsigned Linux 1.14 runtime built and exercised: startup/version, dashboard, offline generation, ZIP, PDF, portable export and Canvas save. Linux install/repair/rollback/uninstall/tamper/copy-failure/data-preservation lifecycle was exercised. Windows/macOS execution and signing were not performed.
- NPM audits for Cloud, Sales and Svelte dependencies reported **zero known vulnerabilities**. A clean Python core installation passed dependency consistency and pip-audit reported **no known vulnerabilities**. A conflicting preinstalled sandbox tool was isolated from that clean application environment rather than represented as an application dependency result.

## Decisions and remaining acceptance

- AI-generated lettering remains raster. Editable Canvas layers are real, but existing pixels are not recovered as semantic text. Existing Canvas/storage/export functionality is reused, not falsely called complete vector reconstruction.
- AI mode has three formats; additional basic sizes and logo concepts remain a separately chosen workflow. Padding and web-source compression are disclosed.
- The concept gallery is desirable direction/provenance, **not a successful paid product-output test**. No paid generation, purchases, checkout or deployment was performed.
- Actual paid-model response/quality, brand fidelity, provider invoice cost and latency still require funded owner-authorized runs. Actual service authentication, payment, delivery, object restoration, commercial hosting, legal terms and clean-device/signing checks require the owner's platforms. These are detailed in `../../OWNER-HANDOFF-1.14.md`, not concealed as completed.
- The supplied daily maintenance cron is not a five-minute delivery service. The runbook requires a supported monitored schedule before sales.
- Prior 91-item reconciliation remains preserved as historical context. Its hero-only descriptions are superseded by this release; its external/customer/scope boundaries are not magically marked passed.

**Result:** locally verified complete source delivery with explicit activation/acceptance gates, not an unqualified production-quality, security or satisfaction certificate.
