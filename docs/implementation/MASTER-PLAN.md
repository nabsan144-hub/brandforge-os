# BrandForge OS — FINAL FIX, ADD & VERIFY PLAN

**Consolidated handoff · 11 September 2026**
**Source baseline:** `5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b`
**Purpose:** One implementation document covering the technical audit and the subsequent candid review of the showcased campaign designs.

> **Completeness boundary:** This document includes every finding and recommendation identified in those reviews. It is not a guarantee that the product has no other defects. Production credentials, customer accounts, paid generation, payments, email delivery and OS-specific installation were not exercised end-to-end. Their verification tasks are included below rather than falsely marked complete.

**This is a specification and backlog, not a claim that fixes have been implemented. All checkboxes start open.** Where functionality already exists, the task is to verify or improve it, not blindly rebuild it.

## Implementation status

The original backlog below remains intact. Current: `PROGRESS.csv` and `../audit/FOLLOW-UP-1.12.0.md`. This pass adds reviews, content archives, private vector versions/layout edits, bounded image recovery, optional metrics and an unsigned native build candidate. This is not completion of all original acceptance criteria; live, legal, native-device, customer and some universal-editor/design work remains.

## How to use this document

1. Work from the reviewed commit or revalidate findings against the current branch.
2. Create a ticket for every numbered item. Preserve these IDs in commits and tests.
3. Follow the release sequence below. Do not implement optional expansion features before core reliability and output quality.
4. A task is complete only when its acceptance check passes and evidence is attached.
5. The full original audit follows this checklist, with source references, reproduction details, limitations and business analysis. Do not discard those details when creating tickets.

### Work classifications

- **BLOCKER:** Must pass before launching the affected paid feature.
- **FIX:** Confirmed implementation/content defect or high-priority improvement.
- **VERIFY:** Requires staging, operational access, real users or platform testing.
- **ADD:** Product capability recommended for a stronger customer experience; not automatically a launch blocker.
- **DECIDE:** Business or product policy requiring explicit owner approval.
- **LATER:** Expansion to defer until the core proposition is validated.

## Release sequence

**Gate A — paid image safety:** T01–T06, T09, V03, V04, V06.
**Gate B — credible customer experience:** T07–T08, T10–T11, T15, Q01–Q16, U01–U05, U09, M01–M09.
**Gate C — real paid operations:** T12–T14, O01–O09, V01–V15, B04–B07.
**Gate D — expansion:** customer validation first, then selected U06–U08/U10–U12 and B08–B12.

The gates describe priorities, not permission to ignore an applicable security, privacy or legal requirement. A closed checkout is preferable to opening an unverified money flow.

---

# PART I — MASTER IMPLEMENTATION CHECKLIST

## A. Technical fixes — preserve the original audit IDs

### T01 / F01 — Enforce truthful no-AI behavior [BLOCKER]
- [ ] Separate text-provider selection from image-generation consent.
- [ ] Add an unambiguous mode that disables every model-provider call.
- [ ] Enforce that decision server-side for Free, Pro and Agency; do not rely on UI state.
- [ ] Show the resolved image provider and which brand fields will be transmitted before Create.
- [ ] Include that decision in the saved brief/execution metadata and idempotency semantics.
**Done when:** Tests intercept zero provider requests in no-AI mode for all plans; choosing a text provider does not silently authorize a different image provider.
**Start in:** `cloud/api/_lib/routes/campaigns.js`, `engine.js`, `keys.js`, `cloud/public/app.js`, `index.html`.

### T02 / F02 — Include image spend in monetary budgets [BLOCKER]
- [ ] Resolve all planned text/image operations before starting work.
- [ ] Reserve their combined operator-funded cost atomically, including offline/BYOK text plus operator imagery.
- [ ] Account for model, quality, retries and charged work whose save later fails.
- [ ] Add image-specific budget configuration and an image kill switch.
- [ ] Missing/invalid image pricing must not permit unbudgeted image work.
**Done when:** Concurrent requests cannot exceed the configured reservation ceiling; BYOK/offline text does not bypass image accounting; the user gets a clear fallback/no-charge explanation.
**Start in:** `cost.js`, `visuals_ai.js`, `campaigns.js`, cost-guard migration and maintenance alerts.

### T03 / F03 — Make campaign assets payload-safe [BLOCKER]
- [ ] Prefer private object storage for binary imagery, with owner-scoped retrieval and expiring authorization.
- [ ] Return asset metadata rather than large base64 images in every campaign JSON response.
- [ ] Until storage migration is complete, bound the entire serialized response, not only decoded image bytes.
- [ ] Normalize/compress scenes and budget for SVG paths, logos, variants and metadata.
- [ ] Preserve portable ZIP exports and account export after changing asset storage.
**Done when:** Largest supported realistic paid campaign saves, opens, exports and downloads on deployed staging without payload errors or cross-account asset access.
**Start in:** `visuals_ai.js`, `engine.js`, `camp-id.js`, `me-export.js`, `workspace-tools.js`, storage policies/migrations.

### T04 / F04 — Persist and display image status [BLOCKER]
- [ ] Add a migration for image stage metadata, or integrate it consistently into the existing stage model.
- [ ] Distinguish not requested, not entitled, not configured, generated, failed and fallback states.
- [ ] Save provider, model and bounded diagnostic codes; never provider secrets or unnecessary sensitive payloads.
- [ ] Return the status on create/detail and include it in exports/manifests.
- [ ] Display paid enhancement failures and provide a targeted recovery path.
**Done when:** Every image state survives database save, reload and export; support can understand what happened without guessing from the final picture.

### T05 / F05 — Correct OpenAI and model-specific contracts [BLOCKER for enabled provider]
- [ ] Remove `response_format` for GPT image models where unsupported.
- [ ] Use provider/model-specific request builders rather than shared assumptions.
- [ ] Align requested dimensions with the intended landscape composition; do not request square while promising wide artwork.
- [ ] Set supported output format/compression intentionally.
- [ ] Add negative contract tests and a capped-spend real smoke test for each enabled provider/model.
**Done when:** The actual configured request is accepted by its provider and invalid fields/models are caught before release. Do not treat successful mocks as proof.
**Start in:** `cloud/api/_lib/visuals_ai.js`, provider tests.

### T06 / F06 — Correct provider provenance and rights notices [BLOCKER]
- [ ] Replace hard-coded Gemini attribution with actual persisted provider/model data.
- [ ] Record generation time and relevant output metadata.
- [ ] Replace blanket commercial-rights assurances with accurate, neutral review guidance.
- [ ] Keep provider terms separate from input, trademark, likeness and advertising rights.
**Done when:** Gemini/OpenAI/xAI files identify the correct source and never inherit another provider's terms language.
**Start in:** `engine.js` guidelines generation, export metadata.

### T07 / F07 — Fix both light-theme contrast defects [FIX]
- [ ] Homepage `.term-bar > .mono`: use inverse text appropriate to its dark surface; measured failure was 3.07:1.
- [ ] Pricing `.text-muted\/80`: remove problematic opacity/use an accessible opaque color; measured failure was 3.83:1.
- [ ] Test small normal text at a minimum 4.5:1, including nested surfaces and revealed sections.
**Done when:** Both defects pass in live/staging light mode and the real-browser regression suite, at mobile and desktop widths.

### T08 / F08 — Make availability statements consistent [FIX]
- [ ] Replace “Desktop early access open” with the actual current state while it is waitlist-only.
- [ ] Explicitly identify Free availability, paid-upgrade availability and Desktop availability.
- [ ] Derive badges, pricing cards and CTAs from one authoritative release state.
- [ ] Prefer a successful public capability/status response for expected closed-checkout UI, while keeping payment actions fail-closed.
**Done when:** Visitors can tell what can be used/bought today without an FAQ search or misleading CTA; closed paid checkout does not look like an accidental outage.

### T09 / F09 — Resolve hero-only AI imagery expectations [FIX / DECIDE]
- [ ] Choose: disclose “AI scene on hero only; resized variants are vector-only,” or implement imagery consistently across advertised formats.
- [ ] If implementing, reuse one stored scene and compose format-specific crops; do not duplicate large base64 blobs in database rows.
- [ ] Protect headline, CTA, product and logo safe areas for each ratio.
**Done when:** Every advertised format receives exactly the artwork treatment the customer was promised.

### T10 / F10 — Keep edited copy and visuals synchronized [FIX / ADD]
- [ ] Introduce canonical editable headline, offer, price/terms, CTA and destination fields.
- [ ] Re-render deterministic visuals from those fields without charging a new full AI campaign.
- [ ] Mark dependent visuals stale after relevant text changes.
- [ ] Prevent an unnoticed mismatch in exported packs; require regeneration or explicit acknowledgment.
- [ ] Preserve old revisions and consistent restore behavior.
**Done when:** A price/CTA correction updates the pack without a full campaign rerun, and restored versions remain internally consistent.

### T11 / F11 — Run browser regressions in CI [FIX]
- [ ] Add isolated preview startup, Chromium installation, harness execution and teardown.
- [ ] Propagate failing exit codes; attach screenshots and JSON evidence on failure.
- [ ] Test dark/light, revealed content, responsive widths, exports and relevant authenticated fixtures.
- [ ] Add F01–F06 regressions at request, database and provider-contract boundaries.
**Done when:** Either observed contrast failure or an image metadata/budget regression causes CI to fail.
**Start in:** `.github/workflows/ci.yml`, `scripts/browser_regressions.py`, Cloud tests.

### T12 / F12 — Improve paid download recovery [FIX]
- [ ] Replace the weak once-daily/three-order independent recovery path with a durable queue or sufficiently frequent supported scheduling.
- [ ] Define backlog throughput, backoff and a delivery target.
- [ ] Alert on oldest undelivered paid order and delivery failures.
- [ ] Add audited support retry/recovery and a customer-visible delivery status.
**Done when:** A simulated 20-order email outage clears within the agreed target after recovery, without duplicate charges or uncontrolled duplicate emails.

### T13 / F13 — Verify and configure signup abuse defenses [VERIFY / FIX]
- [ ] Verify actual Supabase rate limits, email-confirmation policy and challenge enforcement.
- [ ] Resolve the empty public `captchaSiteKey` deliberately rather than assuming protection is enabled.
- [ ] Keep client and server challenge configuration in sync.
- [ ] Monitor signup velocity, confirmation failures and first-generation abuse; provide accessible recovery.
**Done when:** Abuse is constrained without creating a legitimate-user signup dead end. An empty key alone is not proof of an auth bypass.

### T14 / F14 — Repair release provenance [FIX]
- [ ] Separate historical manifests from the current release manifest.
- [ ] Align README, changelog, runtime/update metadata, source tier and release artifact version.
- [ ] Build and checksum immutable shipping artifacts from an identifiable commit/tag.
- [ ] Expose a non-sensitive deployed build ID.
**Done when:** A support ticket, purchase, ZIP and deployment can each be mapped to the correct version/commit/checksum. Verify actual private ZIPs separately from the repository.

### T15 / F15 — Publish one supported Desktop setup flow [FIX]
- [ ] Replace the homepage root-level `requirements.txt` snippet with the actual supported setup-helper/virtual-environment flow.
- [ ] Keep Windows/macOS/Linux instructions consistent with `START-HERE.md`.
- [ ] Test fresh machines; do not assume Python installed means dependencies work.
- [ ] Keep terminal-heavy instructions off the primary Cloud acquisition journey.
**Done when:** A new user following only the published instructions reaches a first working campaign on every advertised platform.

## B. Generated design quality — fix the product output, not just its container

These are visual judgments from the supplied screenshots, not measured conversion statistics. Validate improvements at actual output dimensions and with target customers.

### Q01 — Set an explicit publishable-output standard [FIX / DECIDE]
- [ ] Define a review rubric: hierarchy, legibility, spacing, brand fit, composition, offer clarity, factual correctness, exact product representation and revision effort.
- [ ] Test typical, not only handpicked, briefs and long/short text.
**Done when:** The owner can demonstrate that ordinary results meet the documented standard, with rejected examples retained for regression tests.

### Q02 — Redesign the vector baseline [FIX]
- [ ] Replace the “headline left, giant colored benefits rectangle right” default with intentionally composed layouts.
- [ ] Reduce the mismatch between huge panels and tiny bullet text.
- [ ] Make the free/template result professionally useful without an AI background rescuing it.
**Done when:** Vector-only work is credible as a publishable choice, not a deliberately weak upgrade comparison.

### Q03 — Repair typography and hierarchy [FIX]
- [ ] Define format-aware type scales, line lengths, headline wrapping and spacing.
- [ ] Avoid oversized generic headlines plus unreadably tiny benefits.
- [ ] Define overflow/truncation behavior and a preview warning instead of silently losing important terms.
**Done when:** Headlines, offer and critical terms remain readable at intended viewing size for realistic brief lengths.

### Q04 — Remove repetitive gold/glass CTA styling [FIX]
- [ ] Remove stacked oval shadows/shiny edges as a universal button treatment.
- [ ] Make CTA appearance brand- and format-specific; use simple action text where a fake UI button is inappropriate.
**Done when:** CTA styling supports the message and no longer gives unrelated brands the same obvious generator signature.

### Q05 — Use meaningful, aligned icons [FIX]
- [ ] Replace generic symbols unrelated to their benefit text, or omit them.
- [ ] Align icon weight, scale, text and spacing; prioritize the benefit over decoration.
**Done when:** A viewer can understand each symbol's relationship to the message without explanation.

### Q06 — Build distinct composition families [ADD]
- [ ] Product-first: approved product imagery, one clear benefit and offer.
- [ ] Offer-first: promotion/price, important terms and action.
- [ ] Editorial: strong headline with restrained imagery.
- [ ] Service-first: relevant service context, specific value and booking action.
- [ ] Typography-led: deliberate expressive type rather than empty rectangles.
- [ ] Evidence-led: only supplied, verified proof; never invented testimonials/statistics.
**Done when:** The engine chooses an appropriate structure and can omit unnecessary fields rather than forcing every ad into headline/subheadline/three bullets/button.

### Q07 — Make brand identity genuinely client-specific [FIX / ADD]
- [ ] Demonstrate actual customer logos, suitable type treatment, palette and tone.
- [ ] Do not treat an initials badge as a convincing final identity by default.
- [ ] Avoid making unrelated client campaigns look like BrandForge's own navy/gold brand.
**Done when:** A blind comparison can distinguish different brands without relying solely on the brand name.

### Q08 — Add approved product/reference-image support [ADD]
- [ ] Distinguish logo upload from product imagery/reference photography.
- [ ] Preserve actual product appearance where fidelity matters; disclose any generated substitution.
- [ ] Add input rights/privacy controls and clarify when providers receive images.
**Done when:** A customer can create an ad for their real product, not a plausible but unrelated generated product.

### Q09 — Improve text/image composition and safe areas [FIX]
- [ ] Keep subjects and products away from critical text.
- [ ] Use deliberate overlays or negative space instead of relying on accidental image contrast.
- [ ] Adapt crop, layout and information density per aspect ratio.
**Done when:** No important content is obscured, awkwardly cropped or unreadable in square, story, portrait and landscape outputs.

### Q10 — Rebuild the Northline Coffee showcase [FIX]
- [ ] Add a coherent coffee-specific visual or stronger intentional typography.
- [ ] Correct weak benefit hierarchy, disconnected icons, provisional-looking identity and dated CTA decoration.
- [ ] Establish a clear focal point and useful offer/message.
**Done when:** It demonstrates an output a café could reasonably choose to publish, not simply a successful file-generation test.

### Q11 — Improve the Karak example [FIX]
- [ ] Retain the atmospheric tea subject while controlling headline/image competition.
- [ ] Reduce dense small text and improve hierarchy.
- [ ] Treat queue/delivery claims as supplied fictional sample claims, not verified facts.
**Done when:** The promotion reads quickly, maintains tea/brand character and does not rely on unsupported claims for persuasion.

### Q12 — Improve the fitness example [FIX]
- [ ] Replace generic category messaging with brief-grounded value.
- [ ] Test a real service/people-focused or offer-focused direction instead of relying only on equipment imagery.
**Done when:** The creative communicates why this particular gym/session is relevant, without inventing differentiation.

### Q13 — Improve the skincare example [FIX]
- [ ] Separate headline and product focal areas.
- [ ] Improve supporting-copy readability and use exact approved products where required.
- [ ] Validate health/sensitive-skin/time-to-result claims against supplied proof.
**Done when:** The ad is legible and product-faithful, with no implied evidence the customer did not provide.

### Q14 — Improve the property example [FIX]
- [ ] Use the actual property when advertising a listing; clearly label conceptual imagery when appropriate.
- [ ] Replace generic value claims with accurate supplied specifics.
- [ ] Protect text contrast over architecture and landscape.
**Done when:** The creative cannot reasonably be mistaken for photographs or verified features of an unrelated property.

### Q15 — Review Urdu/Hindi as advertising typography, not only glyph rendering [FIX / VERIFY]
- [ ] Have fluent reviewers assess wording, hierarchy, shaping, line breaks, punctuation and mixed-script text.
- [ ] Rebalance the large yellow Urdu panel and tiny benefit copy shown in the sample.
- [ ] Test PDF/raster/outlined SVG, not only the browser preview.
**Done when:** Native readers judge the ad readable and professionally composed. Correct script rendering is not translation certification.

### Q16 — Demonstrate a complete, usable story output [FIX / VERIFY]
- [ ] Inspect the full story, not only the screenshot's visible crop.
- [ ] Give empty space a deliberate role; establish a focal point and complete action.
- [ ] Respect platform UI safe areas and mobile viewing size.
**Done when:** The full story communicates a useful proposition and action without becoming a stretched landscape template.

### Q17 — Benchmark against the customer's alternatives [VERIFY]
- [ ] Use identical briefs in BrandForge and the actual free/freemium/manual workflows target customers use.
- [ ] Compare blind preference, willingness to publish, editing time, corrections, brand/product accuracy and total cost.
- [ ] Record plan/model/date/limitations; do not claim competing tools are perfect or always free.
**Done when:** Positioning is based on a demonstrated advantage. If output and total effort both lose, improve before scaling acquisition.

## C. Customer experience and additions

### U01 — Guided first campaign and practice sample [ADD]
- [ ] Start with product/brand, audience, offer and benefits; progressively disclose provider/format/advanced controls.
- [ ] Provide a practice/demo brief that does not unexpectedly exhaust the three lifetime campaigns.
- [ ] Preview expected deliverables and provider use before Create.
**Done when:** An uncoached target user understands the form and reaches a useful first result.

### U02 — Make campaign allowance rules explicit [FIX / DECIDE]
- [ ] Explain what consumes an allowance, including saved template fallbacks.
- [ ] Explain daily/monthly/lifetime limits and UTC resets near relevant actions.
- [ ] Agree a clear degraded-result policy and show it before generation.
**Done when:** A user can predict whether an action consumes a campaign; failed unsaved work and free deterministic revisions follow the stated policy.

### U03 — Targeted retries and job visibility [ADD]
- [ ] Show generation state, per-stage progress/status, recoverable errors and a support reference ID.
- [ ] Offer image-only recovery and explain any cost/allowance before retry.
- [ ] Preserve idempotent recovery for uncertain saves; do not encourage accidental duplicate paid work.
**Done when:** Users know whether to wait, retry, check history or contact support.

### U04 — Make final deliverables easy to review and edit [ADD]
- [ ] Support canonical text edits, logo placement controls and appropriate image replacement/crop controls.
- [ ] Clearly distinguish editable source fields from outlined vector paths.
- [ ] Provide a consistent final preview for all assets before export.
**Done when:** Common corrections can be made without starting over or using an unrelated external tool for every adjustment.

### U05 — Clarify output and ownership boundaries [FIX]
- [ ] Describe exact formats, native-document differences, watermarks, hero-only artwork if retained and template-logo limitations.
- [ ] Explain that Cloud/Desktop are separate purchases and not identical pipelines.
- [ ] State rights accurately without guaranteeing exclusivity, trademark clearance or ad approval.
**Done when:** Pricing, app, exported notices and sample downloads tell the same story.

### U06 — Cloud client review and approvals [ADD]
- [ ] Add owner-authorized read-only sharing, expiry/revocation, comments and approval state.
- [ ] Define whether reviewers require accounts and what they may download.
- [ ] Keep review links separate from full account access.
**Done when:** A client can review an intended pack without installing Desktop or receiving broader workspace access.

### U07 — Team roles and permissions [LATER / DECIDE]
- [ ] Until built, describe Cloud as a solo workspace with client brands rather than implying a multi-seat agency system.
- [ ] If demand warrants it, specify organizations, seats, roles, invitations and ownership/billing boundaries before implementation.
**Done when:** Published team claims match actual permission-tested functionality.

### U08 — Desktop/Cloud portability [ADD]
- [ ] Define a versioned campaign import/export schema before promising synchronization.
- [ ] Handle asset transfer, revisions, IDs, rights and unsupported features explicitly.
**Done when:** A supported transfer round-trip preserves content and clearly reports anything omitted. Do not imply seamless sync until it exists.

### U09 — Clarify white-label scope [FIX]
- [ ] Distinguish watermark-free/client-branded output from a custom-domain portal, rebranded app or hosted service rights.
- [ ] Separate Cloud entitlements from Desktop Agency+Source licensing.
**Done when:** A buyer knows exactly what may be rebranded/resold and what is not included.

### U10 — Package Desktop for nontechnical customers [ADD]
- [ ] Evaluate signed installers or packaged runtimes, repair/update flow and supported OS versions.
- [ ] Retain honest first-setup network/dependency disclosures.
**Done when:** Installation and maintenance fit the advertised nontechnical audience; packaging does not weaken local security.

### U11 — Keep Desktop review securely local [VERIFY / DECIDE]
- [ ] Clearly explain loopback-only review limitations.
- [ ] Do not expose the Desktop server publicly to make client links work.
- [ ] Design any remote review through a separately authenticated, scoped sharing service.
**Done when:** Remote-sharing claims and actual network/security behavior agree.

### U12 — Responsible sensitive-client guidance [VERIFY / ADD]
- [ ] Review clinic/legal examples and distinguish local storage from broader regulatory suitability.
- [ ] Document OS access protection, encrypted backups, retention and explicit provider opt-in.
**Done when:** Sales copy makes no unsupported compliance or blanket privacy promise.

## D. Marketing, design system and conversion

### M01 — Unify the product promise [FIX]
- [ ] Prefer “Turn a client brief into a branded campaign pack you can review, revise and hand over.”
- [ ] Replace or narrow “your entire marketing department” where it implies unsupported capabilities.
**Done when:** Website/app positioning describes what the Cloud product actually delivers.

### M02 — Shorten the mobile first screen [FIX]
- [ ] Reduce announcement/header density and show useful product proof earlier.
- [ ] Keep one primary action and one quieter sample action.
- [ ] Preserve product distinctions without a wall of implementation detail above the evidence.
**Done when:** A 390px visitor quickly understands the output and next action.

### M03 — Remove decorative-interaction instructions [FIX]
- [ ] Remove the paragraph teaching visitors to scatter the drifting orbs.
- [ ] Keep any animation subtle, nonblocking and reduced-motion aware.
**Done when:** Decoration neither obscures content nor distracts from understanding/starting the product.

### M04 — Put value before implementation explanations [FIX]
- [ ] Lead with useful deliverables, then demonstrate them, then explain limitations concisely.
- [ ] Move detailed deterministic/provider/agent architecture explanations into expandable sections/docs.
- [ ] Keep necessary fictional-sample, manual-edit and rights disclosures next to the relevant claim.
**Done when:** Customers understand what they gain without having to understand the architecture. Important disclosures remain visible and truthful.

### M05 — Replace disconnected thumbnails with a coherent campaign showcase [FIX]
- [ ] Show one brief producing square, story, landscape and matching copy/document deliverables.
- [ ] Show an offer revision updating the relevant assets.
- [ ] Make previews readable at useful size, not only tiny gallery tiles.
**Done when:** The showcase proves campaign consistency and revision, not just background-image generation.

### M06 — Make every showcase reproducible [FIX / VERIFY]
- [ ] Record original brief, plan/mode, dimensions, included assets and whether manual edits occurred.
- [ ] Distinguish illustrated tour from actual creation/edit/export recording.
- [ ] Do not present manually polished exceptions as ordinary engine output.
**Done when:** Another operator can reproduce comparable output from the disclosed input and product version.

### M07 — Replace “nothing is misspelled”/absolute-language claims [FIX]
- [ ] Explain that text is rendered separately from the image model for reliable typography.
- [ ] Do not equate exact vector rendering with correct input, translation, proofreading or untruncated copy.
**Done when:** Language claims match tested capabilities and acknowledge human review.

### M08 — Consolidate design tokens and state styling [FIX]
- [ ] Standardize colors, inverse-surface text, spacing, type, focus, error and success tokens across marketing/Cloud/Desktop implementations.
- [ ] Include opacity and nested dark surfaces in rendered tests.
- [ ] Retain the coherent navy/gold and restrained serif direction unless user testing shows a reason to change it.
**Done when:** Core components are consistent and accessible without forcing client output into BrandForge's branding.

### M09 — Use state-appropriate navigation [FIX]
- [ ] “Start free” for guests; clear plan-management wording for existing subscribers.
- [ ] Avoid “Upgrade” implying checkout is currently available when it is gated.
**Done when:** Every label describes the action the visitor actually receives.

### M10 — Separate Cloud and Desktop decision paths [FIX]
- [ ] State which product fits browser convenience versus local ownership.
- [ ] Maintain the precise comparison matrix, but do not require studying it to take the first step.
**Done when:** Customers can self-select without confusing one-time licensing and recurring access.

## E. Operations, security and maintainability

### O01 — Preserve existing safeguards [VERIFY]
- [ ] Regression-test bearer validation, owner filters, restricted RPCs, quotas, idempotency, optimistic revisions, logo validation, BYOK fail-closed behavior, webhook verification and deletion-before-erasure billing controls.
- [ ] Preserve Desktop loopback/trusted-host/write-capability protection and existing browser security headers.
**Done when:** Feature changes do not weaken controls already present. The normal public Supabase anon key must not be misclassified as a service-role leak.

### O02 — Use an end-to-end execution deadline [VERIFY / FIX]
- [ ] Measure time from request arrival, including auth/database/budget work, provider retries, scene generation and save.
- [ ] Fit all work inside the deployed function configuration; use queued jobs if synchronous deadlines are unreliable.
**Done when:** p95/p99 behavior and timeout recovery are known; no orphaned reservations or ambiguous double work occurs.

### O03 — Manage storage growth and retention [ADD / DECIDE]
- [ ] Budget database, binary assets, backups and egress.
- [ ] Define deletion, retention and orphan-asset cleanup consistent with account export and financial records.
**Done when:** Growth and cleanup are measurable, and deleting a record neither leaks nor accidentally removes another owner's asset.

### O04 — Add operational readiness monitoring [ADD]
- [ ] Keep public health minimal; add protected dependency/readiness checks.
- [ ] Monitor auth/database/provider/billing/fulfillment customer journeys rather than treating HTTP 200 health as full readiness.
**Done when:** Relevant dependency failures produce useful alerts with an assigned owner.

### O05 — Prove backups and recovery [VERIFY]
- [ ] Document RPO/RTO, restore process and encrypted-key recovery.
- [ ] Verify restored state reconciles safely with external billing.
**Done when:** A restore drill succeeds and evidence is retained.

### O06 — Maintain a dependency/security update policy [ADD / DECIDE]
- [ ] Add scheduled dependency scans and an inventory/license record.
- [ ] Define severity thresholds, remediation deadlines and explicit exceptions.
- [ ] Replace silent report-only handling with a deliberate policy; do not claim “no vulnerabilities” beyond the scan's scope/time.
**Done when:** Findings produce actionable tickets or documented risk acceptance.

### O07 — Define support operations [ADD / DECIDE]
- [ ] Publish realistic support hours, contact route, delivery recovery and what “priority” means.
- [ ] Give support access only to necessary diagnostics, with audit trails and secret redaction.
**Done when:** Customers know how to recover, and the operator can resolve problems without ad hoc production changes.

### O08 — Review seller, license and privacy information [VERIFY]
- [ ] Confirm seller/entity details, launch-market terms, refund process, renewal language and prelaunch-candidate license approval.
- [ ] Publish understandable providers/subprocessors, data flows and retention practices.
- [ ] Clarify encrypted key storage versus end-to-end encryption; avoid unsupported “secure” guarantees.
**Done when:** Appropriate owner/legal review is complete and all sales/checkout/app notices agree.

### O09 — Establish release evidence and rollback [ADD]
- [ ] Attach test results, provider smoke evidence, migration compatibility and artifact checksums to each paid release.
- [ ] Document rollback and feature kill switches, including how old campaign records remain readable.
**Done when:** A release can be explained, rolled back safely where feasible, and supported by exact version evidence.

## F. Business decisions and validation

### B01 — Choose a specific initial segment [DECIDE]
- [ ] Test solo marketers/small agencies doing repeat local/service-business campaigns, including multilingual needs.
- [ ] Treat this as a hypothesis, not established demand.
**Done when:** One initial segment and its core recurring job are explicit.

### B02 — Sell a demonstrated advantage [DECIDE / VERIFY]
- [ ] Choose the proven advantage: better output, less effort, reliable consistency or an otherwise unavailable capability.
- [ ] Do not sell engine complexity, agent count or file quantity as substitutes for useful work.
**Done when:** Benchmarks and customer observations substantiate the main promise.

### B03 — Validate pricing against actual cost [VERIFY / DECIDE]
- [ ] Model full-utilization revenue: Pro monthly $0.98/campaign; Pro annual about $0.817; Agency $0.33.
- [ ] Include text/images/retries, payment fees, refunds, hosting, storage, support and acquisition.
- [ ] Evaluate transparent image allowances/credits if costs vary too much for one undifferentiated campaign quota.
**Done when:** Pricing survives realistic utilization and failure scenarios; hypothetical costs are not presented as provider quotations.

### B04 — Reserve for Desktop maintenance/support [DECIDE]
- [ ] Model one-time revenue against installation support, 24-month maintenance and source-tier onboarding.
- [ ] State supported platforms and post-maintenance expectations.
**Done when:** The one-time offer is financially supportable without invented perpetual-support promises.

### B05 — Separate Source/resale buyers [FIX / ADD]
- [ ] Create a distinct path with clear rights, operating requirements and third-party costs.
- [ ] Explain public source inspection versus proprietary commercial rights.
**Done when:** Buyers do not mistake source access for an operated SaaS business or unrestricted open-source redistribution rights.

### B06 — Instrument a privacy-conscious funnel [ADD]
- [ ] Measure visit, signup, email confirmation, first campaign, first export, repeat use and paid conversion.
- [ ] Configure consent/data minimization and relevant CSP origins where required.
**Done when:** Events are validated, deduplicated and do not capture campaign content or provider secrets unnecessarily.

### B07 — Monitor actual delivered value [ADD]
- [ ] Track usable-pack rate, editing time, time to first usable export, fallbacks, image failures, export failures, cost per usable pack, support demand and refunds by cause.
- [ ] Evaluate weekly reviewed-and-exported packs per active customer as a north-star metric.
**Done when:** A dashboard distinguishes useful work from mere generation volume.

### B08 — Run uncoached customer pilots [VERIFY]
- [ ] Observe a small cohort completing real briefs against their existing process.
- [ ] Ask what they would publish and pay for; record corrections and abandonment reasons.
- [ ] Test Desktop/privacy and Source/resale with separate cohorts.
**Done when:** Product decisions use observed behavior rather than compliments or assumed ROI.

### B09 — Define an output/effort go-no-go gate [DECIDE]
- [ ] Agree measurable pilot success thresholds before reviewing results.
- [ ] If BrandForge loses both visual preference and end-to-end effort, improve before scaling acquisition.
**Done when:** Paid growth has an explicit evidence-based approval decision.

### B10 — Avoid unsupported competitive claims [FIX]
- [ ] Acknowledge impressive free/freemium alternatives without asserting universal perfection or permanent free access.
- [ ] Maintain dated, fair comparisons using the same brief and comparable effort.
**Done when:** Competitive messaging can be substantiated and does not rely on dismissing alternatives.

### B11 — Defer feature-count expansion [LATER]
- [ ] Do not prioritize more provider badges, agents, autonomous posting or a huge template catalog over reliable generation, editing and delivery.
**Done when:** Roadmap capacity is allocated to the validated customer bottleneck first.

### B12 — Keep broad positioning ambitions separate [DECIDE]
- [ ] Do not simultaneously claim to replace a design suite, autonomous agency, live SEO auditor, enterprise platform and reseller business.
- [ ] Retain accurate limitations around research, platform approval, compliance and revenue.
**Done when:** Each product page describes one understandable purchase with defensible capabilities.

## G. Final end-to-end verification — do not skip because unit tests pass

- [ ] **V01 — Auth:** Real signup, email confirmation, login/logout and password recovery pass on staging, including expired links and an interrupted session.
- [ ] **V02 — Tenant isolation:** Two staging users cannot access each other's campaigns, brands, revisions, keys, exports, asset URLs or billing actions; actual deployed RLS/RPC policies are verified.
- [ ] **V03 — Privacy:** No-AI mode makes no model calls for every plan; action-level provider disclosures match captured traffic.
- [ ] **V04 — Cost/concurrency:** Combined text/image ceilings, plan limits, duplicate requests, concurrent runs and failed-save recovery behave correctly.
- [ ] **V05 — Provider reality:** Each enabled provider/model completes a capped-spend real smoke test; malformed output, rate limits, unavailable model and timeout cases degrade transparently.
- [ ] **V06 — Maximum assets:** Realistic high-entropy maximum-size campaigns survive staging save/open/download/account export and owner authorization checks.
- [ ] **V07 — Editing:** Price/offer/CTA edits, restores, stale detection and final exports remain internally consistent without unintended extra campaign charges.
- [ ] **V08 — Payments:** Real test-mode checkout, monthly/annual purchase, upgrade/downgrade, cancellation, failed payment and refund behavior match the pricing/terms; production activation follows a separately approved low-value live check.
- [ ] **V09 — Webhooks:** Duplicate, delayed and out-of-order events reconcile safely; identity ownership and subscription state cannot be reassigned by browser data.
- [ ] **V10 — Deletion:** Export-first guidance, subscription cancellation, pending checkout handling, provider outage and retry recovery all work without orphan recurring charges.
- [ ] **V11 — Fulfillment:** Desktop purchase → email → private link → artifact checksum → installation succeeds; expiry/refund/recovery behave as promised.
- [ ] **V12 — Backlog/outage:** Simulated email/provider/database interruptions recover within defined targets with correct quotas, alerts and support diagnostics.
- [ ] **V13 — Desktop OS matrix:** Fresh Windows/macOS/Linux installs, update/repair, offline creation and advertised exports work on explicitly supported versions.
- [ ] **V14 — Browser/accessibility:** Light/dark, 320/390/768/1440 widths, keyboard/focus, zoom, reduced motion, screen-reader spot checks and mobile exports pass; include Safari/Firefox as well as Chromium where supported.
- [ ] **V15 — Restore/release/legal:** Backup restoration, rollback readiness, monitoring/support ownership, artifact provenance and seller/license/privacy/refund sign-off are documented.

---

# PART II — DEFINITION OF DONE & CHANGE HANDOFF

## Required evidence per ticket

| Field | Required content |
|---|---|
| ID | T/Q/U/M/O/B/V identifier, plus original F ID when applicable |
| Baseline | Reviewed commit and current implementation version |
| Problem | User/operator impact and evidence; distinguish confirmed from unverified |
| Implementation | Files, schema changes, config and policy decisions |
| Tests | Unit/contract/database/browser/staging tests appropriate to the boundary |
| Acceptance | The explicit check from this plan, with result and artifact |
| Security/privacy | Changed data flows, permissions, provider transmission and retention |
| Money | Allowance, cost reservation, billing/refund impact if applicable |
| Rollout | Feature flag, migration order, backfill and compatibility plan |
| Recovery | Rollback or forward-fix procedure; readable existing campaigns |
| Documentation | App copy, pricing, sample, docs and export notices updated together |
| Sign-off | Engineering plus relevant product/design/operations approval |

## Do not implement these shortcuts

- Do not fix public sharing by exposing the Desktop local server.
- Do not hide image failures behind a generic successful campaign message.
- Do not improve gallery images manually while claiming they are unedited engine output.
- Do not remove privacy/rights disclosures simply to make marketing shorter.
- Do not charge a full new campaign merely to re-render changed deterministic text.
- Do not use a passing mock provider response as proof of a real integration.
- Do not turn on checkout solely because the prelaunch validator passes.
- Do not claim a complete security audit or market-proven conversion improvement from these tests.
- Do not rewrite the entire application without a demonstrated need.

## Final owner decision

The purchase case must become: **“This gives me a useful, publishable, editable campaign with noticeably less work.”**

It must not remain: **“This generator can place text and an AI image into a template.”**

Preserve the strong defensive engineering and coherent website identity. Raise the average output quality, complete the revision-to-export workflow, then prove the paid journey and economics before increasing acquisition spend.

---

# PART III — ORIGINAL TECHNICAL AUDIT, EVIDENCE & DETAILED RATIONALE

The following original report is retained in full so that none of its findings, caveats, source references, metrics or acceptance guidance is lost. Its original section numbering and F01–F15 IDs are preserved.

# BrandForge OS — engineering, product and business audit

**Review date:** 11 September 2026
**Reviewed source:** `5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b`
**Properties:** [marketing website](https://www.brandforge-os.com/), [Cloud app](https://app.brandforge-os.com/), [source repository](https://github.com/nabsan144-hub/brandforge-os)

## 1. Executive verdict

**There is a credible product here, with substantially better defensive engineering than a typical early-stage AI wrapper. However, I would not open unrestricted paid acquisition or paid image generation yet.**

The strongest idea is not “an entire marketing department.” It is **a repeatable, reviewable campaign handoff: client brief → copy → branded visuals → portable files**, with a separate local-ownership option. The sample downloads, explicit template disclosures, editable text, multilingual typography and separation of Cloud/Desktop rights support that idea.

The biggest weakness is the gap between the newer image-generation feature and the surrounding product infrastructure. Text generation has accounting, status reporting and defensive fallback logic. Images do not yet have equivalent cost accounting, consent, persisted status or delivery-size safety. That is where most of the high-priority findings cluster.

The visual identity is coherent and worth retaining. Do not start with a redesign. Fix the product contract, the image pipeline and the last-mile customer experience first.

### Launch recommendation

| Area | Judgment |
|---|---|
| Public marketing and waitlist | Suitable for continued learning, after correcting availability wording and contrast |
| Free Cloud acquisition | Conditional: verify real signup/email/generation and abuse controls first |
| Paid AI-image campaigns | Hold until F01–F06 are addressed and staging tests pass |
| Paid billing and Desktop fulfillment | Not verified live; keep the existing fail-closed release gate |
| Broad agency positioning | Premature without clearer white-label scope and a stronger review workflow |
| Full rewrite | Not justified by this audit |

**No confirmed critical account-takeover, remote-code-execution or cross-tenant exploit was established. This is not a security certification.**

## 2. Scope, evidence and limitations

No attachments were present in the workspace. I cloned the accessible public repository instead. I did not modify production, create customer accounts, submit payments, send emails, invoke paid providers, or inspect other users’ data.

### What was actually checked

- Source review of Cloud routing, auth helpers, campaign generation, images, provider keys, input validation, billing/fulfillment, deletion, migrations, exports and browser code.
- Targeted Desktop review of the FastAPI boundary, local security, launch instructions, build and tests.
- Live unauthenticated endpoint checks and public browser rendering.
- Desktop/mobile screenshots; dark and light themes; axe accessibility checks.
- Repository browser regression harness using **synthetic authenticated Cloud fixtures**, not a real account.
- Local provider stubs and real PostgreSQL-compatible PGlite migrations to reproduce selected defects.
- Sampled link/asset checks, deployed frontend/source parity, dependency checks and external API documentation.

### Verification results

| Check | Result |
|---|---|
| Cloud Vitest | **204 tests passed**, 25 files |
| Desktop pytest | **412 passed**, one Pillow deprecation warning |
| Ruff | Passed |
| Marketing npm test | Passed, including 54 demo checks, 14 page a11y checks and CSS/theme gates |
| Desktop Svelte/Vite production build | Passed |
| Schema synchronization | Passed |
| Prelaunch configuration validator | Passed in **PRELAUNCH SAFE**, explicitly not revenue-ready mode |
| Cloud npm audit | No known vulnerabilities reported |
| Python requirements pip-audit | No known vulnerabilities reported |
| Repository browser harness | **Failed:** 97 result records, four contrast-violation instances representing two defects; no reported overflow or page errors |
| Live dark/default pages | Home, pricing and login at 390px and 1440px: no axe violations or horizontal overflow in checked states |
| Live light theme | Same two contrast defects reproduced on home/pricing at 390px; signup had no axe violations |
| Sampled internal links/assets | **49 HEAD checks**, no HTTP error responses |
| Selected deployed files | Five files matched repository bytes exactly: home HTML, sales config, Cloud HTML, app.js, workspace-tools.js |

The pricing page makes a public billing-token request that returns **503, “Paid checkout is not open yet.”** This is an intentional release gate, not evidence of a broken charge. Its browser console error is noise worth improving, but not the core problem.

### Not proven by these results

Real Supabase RLS deployment, production migrations, account confirmation/reset emails, actual provider output quality, payment/refund lifecycle, real ZIP fulfillment, restore-from-backup, real-browser Safari/Firefox behavior, Windows/macOS installs, and production concurrency/load remain unverified. The live frontend match does **not** prove the deployed backend revision matches this commit. The audit is broad and targeted, not a line-by-line proof of every file.

## 3. Prioritized findings

**Priority:** P1 = resolve before the affected paid feature launches; P2 = fix soon; P3 = improvement.
**Evidence:** Live = observed public behavior; Reproduced = local controlled test; Source = directly traceable implementation; Risk = consequence still requiring environmental validation.

### F01 — “Templates only — no AI provider” can still invoke an image provider

**P1 · Reproduced / source · Privacy and product contract**

The selector is under “Text generation provider,” but its option says “Templates only — no AI provider.” For Pro/Agency, the server sets `input.visuals_ai` solely from the plan. `runCampaign()` starts image generation whenever that flag and an operator image key exist, regardless of `provider: 'offline'`.

A local test with an offline text selection and paid-plan input still attempted a Gemini image request containing the brand name, industry and audience. No real provider was contacted; the outbound request was captured by a stub.

**Evidence:** `cloud/api/_lib/routes/campaigns.js:66–70`; `cloud/api/_lib/engine.js:103–107`; `cloud/api/_lib/keys.js` (`resolveCampaignKeys`); `evidence/local-reproductions.json`.

**Customer impact:** A user can reasonably believe their brief will not go to an AI provider. A different operator-selected image provider can also receive context when the user explicitly chose a particular text provider. The site discloses operator image providers generally, but the action-level disclosure is insufficient.

**Fix:** Separate controls for text and imagery. Show the resolved image provider and transmitted fields before Create. Make “No AI providers” disable both paths, enforced server-side. If the intent is text-only control, rename it “Template text; imagery controlled separately,” with an explicit imagery toggle.

**Acceptance:** Offline/no-AI mode causes zero model-provider requests for every plan. Changing a text provider never silently grants permission to a new image provider.

### F02 — Image spend is outside the dollar-based operator budget

**P1 · Reproduced / source · Cost exposure**

`reserveOperatorBudget()` exits unless the **text** key source is `operator`. Its reservation covers text token rates only. Images always use operator credentials and are not included. With personal text keys or offline text, a paid image can run with no dollar-budget RPC at all.

**Evidence:** `cloud/api/_lib/cost.js:5–14`; `cloud/api/_lib/visuals_ai.js:9–16`; `cloud/api/_lib/routes/campaigns.js:88–92`; `supabase/migrations/0010_cost_guard.sql`.

The local reproduction observed **zero budget RPC calls** while an image request was attempted. Existing daily campaign, attempt and global count limits still apply; this is not unlimited unthrottled generation. It is a bypass of the advertised/configured **monetary** guard.

**Fix:** Resolve an execution plan first, reserve text and image budgets atomically before either request, track image provider/model/quality costs, and add an image-specific kill switch. Account for retries and provider charges on failed saves. Do not assume BYOK means zero operator cost.

**Acceptance:** The configured total dollar ceiling protects text plus image spend, including when text is offline or personal-key funded. Missing image pricing fails closed for images, with a clearly disclosed vector alternative.

### F03 — Accepted image sizes can make saved campaigns too large to retrieve

**P1 · Reproduced size defect; deployment failure risk**

`generateScene()` accepts decoded images up to `4.5 * 1024 * 1024` bytes. The image is then base64-embedded in the hero SVG, stored with the campaign and returned inside campaign JSON. Base64 expands the image by approximately one third, before SVG paths and JSON overhead.

A synthetic **3,600,000-byte** provider payload passed the guard and produced **5,000,582 bytes** of serialized engine output; the hero SVG alone was **4,821,469 bytes**. This test proves the size arithmetic and missing end-to-end guard; it is not an image-quality or image-decoding test.

`GET /api/campaigns/:id` returns the full row through ordinary JSON; it is not streaming or gzip-compressed by the application. Vercel documents a **4.5 MB request/response body limit**. The create endpoint returns a small ID response, so a possible failure mode is “generation saved and quota consumed, but opening the campaign fails.” Actual platform behavior for such a production campaign was not exercised.

**Evidence:** `cloud/api/_lib/visuals_ai.js:76–84`; `cloud/api/_lib/engine.js:138–155`; `cloud/api/_lib/routes/camp-id.js:10–15`; `cloud/api/_lib/sb.js:19–24`; `evidence/local-reproductions.json`. External reference: [Vercel function limits](https://vercel.com/docs/functions/limitations#request-body-size).

**Fix:** Put binary assets in private object storage; return metadata and short-lived authorized asset URLs. Until then, normalize/compress scenes and enforce a budget on the **complete serialized response**, leaving headroom for all vectors and metadata. Verify both ordinary campaign viewing and account export with realistic high-entropy images.

**Acceptance:** Largest supported paid campaign is saved, opened, downloaded and exported through deployed staging without a platform payload error.

### F04 — Image status and failure reason are lost at save time

**P1 · Reproduced against the shipped database schema**

The engine returns `visual_status`, including `mode`, provider/model and failure reason. `complete_generation()` explicitly inserts selected columns and does not preserve that object. The campaign schema has no corresponding column. The create response also omits it, and the detail UI reports text-stage status only.

I passed `visual_status: {mode:'svg', reason:'VISUAL_RATE_LIMIT'}` to the real migration function using PGlite. The campaign saved successfully, but the fetched row did not contain `visual_status`.

**Evidence:** `supabase/migrations/0007_generation_ledger.sql:113–141`; `cloud/api/_lib/engine.js:137–161`; `cloud/api/_lib/routes/campaigns.js:94–96`; `cloud/public/app.js:273–277`; `evidence/db-reproduction.json`.

**Customer impact:** A paid user can receive a vector fallback without a durable explanation of why the advertised image enhancement is absent. Support cannot reliably distinguish “not configured,” “rate-limited,” “failed,” and “generated” from the saved status.

**Fix:** Persist an explicit image stage in a migration, return it from the API and display it in the pack/manifest. Distinguish not requested, not entitled, unavailable, failed, and generated. Offer an image-only retry policy rather than requiring a whole campaign rerun.

**Acceptance:** Every image state survives save/reload/export, and a failed paid enhancement is visible before the user downloads.

### F05 — OpenAI image request conflicts with the documented contract

**P1 for the OpenAI lane · Source / documented API mismatch**

`callOpenAI()` sends `response_format: 'b64_json'` with the default `gpt-image-1`. OpenAI’s API documentation explicitly says `response_format` is not supported by GPT image models, which already return base64.

**Evidence:** `cloud/api/_lib/visuals_ai.js:59–65`; `evidence/openai-contract.json`; [OpenAI Create image API](https://developers.openai.com/api/reference/resources/images/methods/generate).

The included tests stub successful responses, so they do not establish that the real provider accepts this request. I did not make a paid API call; classify the likely rejection as a contract defect, not an observed live outage.

The adapter also requests a square image while the prompt asks for wide 16:9 composition. That is a separate composition-quality inconsistency.

**Fix:** Use provider/model-specific request builders. Omit unsupported fields for GPT image models, request a supported landscape size, and choose output format/compression deliberately. Validate the real configured model in staging.

**Acceptance:** Contract tests reject unsupported fields; one operator-approved real request succeeds for each enabled provider.

### F06 — Exported image provenance is hard-coded to Google Gemini

**P1 · Reproduced / source · Customer trust and rights**

Regardless of the actual image provider, generated `brand_guidelines.md` says the artwork comes from Google Gemini under Google’s generative-AI terms, followed by a commercial-use assertion. A local OpenAI run produced `provider: 'openai'` while the file still named Gemini.

**Evidence:** `cloud/api/_lib/engine.js:159`; `evidence/openai-contract.json`.

**Fix:** Generate provenance from persisted provider/model metadata. Avoid blanket legal assurances. Include generation time and a neutral rights-review notice linked to the applicable provider terms. Do not imply a provider’s general terms settle trademark, likeness, input or advertising rights.

**Acceptance:** OpenAI, Gemini and xAI exports each identify the correct provider and never inherit another provider’s rights language.

### F07 — Light theme contains two reproducible contrast failures

**P2 · Live and browser-reproduced · Accessibility**

| Location | Selector | Measured contrast | Target |
|---|---|---:|---:|
| Homepage terminal-bar label | `.term-bar > .mono` | **3.07:1** | 4.5:1 |
| Pricing small explanatory copy | `.text-muted\/80` | **3.83:1** | 4.5:1 |

Both are 11px normal text. The repository browser harness reports each at 390px and 1440px, resulting in four instances of two underlying defects. Both were independently reproduced on the live light-themed site at 390px.

**Evidence:** `evidence/live-light-theme.json`; `fixture-qa/browser-verification.json`; `sales/index.html` terminal block and `sales/pricing.html` opacity-muted note.

**Fix:** Give the intentionally dark terminal its own inverse text token rather than the page’s light-theme muted token. Remove opacity from small pricing copy and choose an opaque accessible foreground.

**Acceptance:** Real-browser light/dark axe checks pass with all reveal sections visible; include 320/390/768/1440 widths. Automated checks still need manual keyboard, focus, zoom and screen-reader review.

### F08 — Availability messaging contradicts the current sales state

**P2 · Live · Conversion and trust**

The homepage announcement says **“Desktop early access open.”** The actual Desktop CTA says **join the waitlist**, pricing states checkout goes live at launch, and the live public billing endpoint confirms paid checkout is closed.

Cloud paid cards fall back to “Start free — no card,” while the surrounding copy describes paid features and guarantees. This is safer than taking an unauthorized payment, but it does not tell users when upgrading will be possible.

**Fix:** Use a single capability/release-state source for badges, cards and CTAs. Suggested wording: “Cloud Free available · Desktop waitlist open · Paid upgrades not yet open.” Avoid publishing an invented launch date.

**Acceptance:** A new visitor can answer “What can I use or buy today?” without reading the FAQ or triggering a failed billing request.

### F09 — Paid AI imagery enhances only the hero, not the resized banner set

**P2 · Source / customer-expectation gap**

The engine embeds the scene in `hero_banner.svg` only. Size variants are generated without it. The code intentionally does this to avoid duplicating a large image across many files, which is a valid engineering concern. However, a customer seeing image-rich campaign examples plus “10/21 presets” may expect those resized outputs to retain the same artwork.

**Evidence:** `cloud/api/_lib/engine.js:145–155`; pricing’s preset promises.

**Fix:** Either explicitly label the current offer “AI scene on hero only; resized variants are vector-only,” or store one shared scene and compose consistent exports at download time. Use format-specific crops and text safe areas rather than stretching one hero layout.

**Acceptance:** Each advertised example identifies exactly which purchased formats get artwork; a story export does not unexpectedly lose the campaign’s imagery.

### F10 — Text editing does not update visual copy; fixing a visual costs another campaign

**P2 · Source / fixture-tested behavior · Core workflow friction**

The UI accurately warns that text edits leave visuals unchanged and recommends Reuse brief, which consumes a new campaign. The warning is honest, but the workflow is weaker than the promise of a reviewable pack. An edited offer or CTA can coexist with an old banner inside the same export.

SVG text is outlined for portable script shaping, so it is not a simple editable text layer in an external design tool either.

**Evidence:** `cloud/public/app.js:280–287`; `cloud/public/workspace-tools.js` review notice; `supabase/migrations/0009_workspace.sql` text revision function.

**Fix:** Separate the structured campaign document from its rendered derivatives. Let users edit canonical headline/offer/CTA values and re-render deterministic visuals without consuming another AI campaign. Mark mismatched visuals as stale and prevent an unacknowledged inconsistent export.

**Acceptance:** Correcting a price or CTA updates the final pack without a second full generation. Older versions remain restorable.

### F11 — Real-browser regression coverage is not a CI gate

**P2 · Source and executed test results · Quality process**

CI runs unit, static/DOM, build and prelaunch checks, but not `scripts/browser_regressions.py`. That browser harness exists and found defects while the normal marketing suite passed. The gap is not a lack of tests; it is failing to run the right layer automatically.

**Evidence:** `.github/workflows/ci.yml`; `scripts/browser_regressions.py`; `evidence/fixture-browser.log`.

**Fix:** Add a browser job that starts an isolated preview, installs Chromium, runs the harness, and uploads screenshots/JSON on failure. Keep authenticated fixtures but supplement with staging end-to-end tests. Add the F01–F06 regressions at their appropriate API/database/contract boundaries.

**Acceptance:** Introducing either observed contrast failure makes CI fail. Failed harness exits must propagate rather than being hidden by a later shell command.

### F12 — Desktop delivery recovery is too slow for a paid download business

**P2 · Source / operational risk**

The scheduled maintenance job runs once daily and retries at most three eligible Desktop orders per invocation. Primary webhooks and provider retries can deliver earlier, so this does **not** mean every buyer waits a day. It means the independent recovery path is shallow during a sustained outage or missed webhook.

**Evidence:** `cloud/vercel.json` cron `0 3 * * *`; `cloud/api/_lib/routes/maintenance.js` `.limit(3)`; `cloud/api/_lib/fulfillment.js`.

**Fix:** Use a durable queue or a sufficiently frequent scheduler supported by the deployment plan. Alert on the oldest undelivered paid order, not just a retry count. Add a support recovery action with an audit trail and a visible delivery status page.

**Acceptance:** Simulate 20 paid orders during an email outage; after recovery, all are delivered within a documented target without duplicate charges or uncontrolled duplicate email.

### F13 — Public CAPTCHA configuration is empty

**P2 · Live configuration observation; abuse risk unverified**

The live `/api/config` returns `captchaSiteKey: ''`, so the shipped client has no CAPTCHA challenge configured. This does not prove Supabase lacks rate limits or other protection, and it is not by itself an auth bypass.

**Evidence:** `evidence/live-api.json`; `cloud/api/_lib/routes/config.js`.

**Fix:** Verify the actual Supabase signup policy and email-confirmation requirement, implement coherent client/server challenge configuration where needed, and monitor signup velocity, confirmation failures and first-generation abuse. Preserve accessible recovery paths.

**Acceptance:** Automated signup bursts cannot cheaply consume email/provider resources, and legitimate users are not trapped by a client/server CAPTCHA mismatch.

### F14 — Release provenance and version labels are stale

**P2 · Source / local comparison**

The changelog starts at **1.9.0**, while the README lead and root release manifest say **1.4.2**. The manifest names a different commit and many old paths. Against the post-build audit checkout, the manifest comparison found 279 matches, 94 changed files and 23 missing files. Some generated build differences can be audit-build artifacts; the old version, commit and relocated API paths independently establish that the manifest is not a manifest of this reviewed tree.

**Evidence:** `README.md`; `CHANGELOG.md`; `RELEASE-MANIFEST.json`; `evidence/manifest-check.json`.

This does not prove any privately fulfilled ZIP is wrong; that artifact was not accessible.

**Fix:** Label historical manifests as historical, generate each shipping manifest from an immutable tag/artifact, and expose the deployed build ID. Keep customer documentation, download version, checksum and update metadata aligned.

**Acceptance:** Support can map a purchase/download/deployment to exactly one commit and artifact checksum.

### F15 — Homepage Desktop quick-start is weaker than the actual supported installer flow

**P2 · Source/live copy · Onboarding**

The homepage’s Unix snippet says `pip install -r requirements.txt` and then `cd app && python server.py`, although the source root has no `requirements.txt`. The canonical `START-HERE.md` instead uses the setup helper and a managed virtual environment. The raw-server snippet also encourages bypassing those setup checks.

**Fix:** Publish one tested command sequence per supported OS, copied from the canonical installer guide. Keep terminal-heavy instructions off the main Cloud acquisition path. For paid nontechnical Desktop customers, prioritize a signed installer or packaged runtime.

**Acceptance:** A fresh user following only the homepage instructions reaches a working first campaign on each advertised platform.

## 4. Backend and security assessment

### Controls worth preserving

- Bearer tokens are validated through Supabase Auth rather than merely decoded.
- Reviewed campaign/brand handlers constrain access by authenticated owner ID.
- Sensitive RPCs and tables are restricted to the service role in the migrations; database tests exercise important boundaries.
- Quota accounting uses reservation/completion transactions and idempotency. Deleting campaign content does not reset completed usage.
- Revisions use optimistic concurrency rather than blindly overwriting another version.
- Logo uploads are bounded, validated and normalized; URLs and brief fields have explicit checks.
- BYOK errors fail closed rather than silently switching a customer’s provider/credit source.
- Webhooks verify HMAC signatures with time tolerance, claim events, handle duplicates and reconcile subscription state.
- Billing ownership is tied to server-authorized checkout evidence, not simply trusting a browser-supplied plan.
- Account deletion attempts to reconcile/cancel billing before erasing the identity.
- Desktop has loopback-peer and trusted-host restrictions plus a write capability; it is not advertised in its technical docs as a public multi-user server.
- Live headers include CSP, HSTS, nosniff and frame restrictions. The public Supabase **anon** key is expected client configuration, not a leaked service-role secret.

### Remaining operational risks to validate

1. **Production RLS:** run two test users against the actual staging database, verifying cross-account reads/writes, revisions, brands and exports fail. Local migrations cannot certify deployment settings.
2. **Serverless deadlines:** text retries and a 45-second image call share a configured 60-second function. The engine deadline begins after auth, quota and budget work. Measure end-to-end p95/p99, not only model time; a request-level deadline or queued job is safer under load.
3. **Storage growth:** base64 assets in JSON rows increase database, backup, egress and export pressure. Introduce private asset storage with a retention policy.
4. **Observability:** `/api/health` verifies runtime response, not auth/database/provider/billing readiness. Keep it public and minimal; add protected dependency checks and synthetic customer-journey monitoring.
5. **Backups:** prove a restore, including encrypted-key recovery and correct billing reconciliation. Document RPO/RTO instead of assuming the hosting provider’s default is sufficient.
6. **Supply chain:** the audited Cloud/Python dependency checks were clean, but that is point-in-time. Add scheduled scans, full dependency/license inventory, and a policy for fixing or explicitly accepting findings. Python CI currently treats the audit as report-only.
7. **Desktop client review links:** the runtime is loopback-only. Treat those as local review tools unless a separately secured remote-sharing mechanism is deliberately built. Do not “fix” shareability by exposing the Desktop server to the internet.
8. **Sensitive-client suitability:** local storage helps, but clinic/legal examples need much more than a privacy tagline: OS account protection, encrypted backups, provider opt-in, access controls, retention guidance and jurisdiction-specific review.

## 5. Frontend, design and theme assessment

### Keep

- The dark navy/near-black and warm gold identity.
- Geist plus the restrained serif headline contrast.
- Readable, spacious authentication layout and clear primary buttons.
- A real downloadable sample instead of unsupported testimonial claims.
- Responsive layouts: no horizontal overflow in the checked public states or fixture harness.
- Visible distinctions between template and generated text.
- Self-hosted fonts and vendored browser dependencies.
- Shared theme preference across the marketing/app subdomains in the implementation.

### Change next

**1. Shorten the first screen.** On the 390px screenshot, the announcement bar, hero, three CTAs, orb instructions and product distinctions push useful product proof below the first screen. Show one concrete output earlier. Keep one primary action and one quieter sample action.

**2. Remove the orb instruction paragraph.** “Click anywhere … watch them scatter” teaches a decorative interaction rather than the product. Keep subtle motion if desired, honor reduced motion, and never make it compete with the CTA.

**3. Unify the promise.** The website’s “Less blank-page work” is more defensible than the app’s “Your marketing department.” The latter invites expectations of publishing, analysis, research, approvals and teams that the Cloud product does not currently satisfy.

**4. Use state-appropriate navigation.** “Upgrade” on the logged-out screen works by switching to signup, so it is not broken, but “Start free” is the clearer guest label. Use “Manage plan” for paying customers.

**5. Design the product, not only the landing page.** A first-campaign wizard should ask for a brief, preview expected deliverables/provider use, then progressively reveal optional controls. Twenty-one format chips should not be the first thing a nontechnical customer has to understand.

**6. Make artwork editing a core interaction.** The biggest design deficiency is not color or rounded corners. It is the inability to easily revise the actual deliverable after reviewing it.

**7. Do not equate portable typography with error-free language.** Outlining text prevents image-model gibberish, but does not prove user input, AI copy, truncation or translation is correct. Replace “nothing is misspelled” with “Typography is rendered separately from the image model for reliable text rendering.”

**8. Consolidate design tokens.** Marketing, static Cloud and Svelte Desktop share a visual direction but have separate implementations. Standardize color, inverse-surface text, focus rings, error/success, spacing and type tokens. Test rendered combinations, including opacity and nested dark surfaces.

## 6. Customer perspective: what is missing?

| Customer question | Current experience / gap | Recommended response |
|---|---|---|
| What can I use today? | Free, paid promises and waitlist language mix | Explicit current availability next to each CTA |
| What counts as a campaign? | Limits are documented, but fallbacks and rerenders are surprising | Show the exact charge/allowance event before generation |
| Will a template fallback spend one of my three attempts? | A saved pack consumes one campaign, including labeled fallback | Offer a free practice/demo brief and an explicit degraded-result policy |
| Can I fix one word on the banner? | Text edits do not update visuals | Free deterministic re-render from editable structured fields |
| Does every banner have the AI scene? | Only the hero does | Accurate format labels or consistent artwork per format |
| Where is my data sent? | Text selector does not control the image provider | Per-action provider disclosure and no-AI mode |
| Can I use my exact product photo? | Logo upload and generated scenes are not product-faithful reference photography | Add approved product/reference-image support with rights and privacy controls |
| Can my client approve without installing anything? | Cloud has no equivalent remote approval workflow in reviewed routes/UI | Read-only share links, expiry, comments and approval states |
| Can my team work here? | Reusable client brands, but no demonstrated Cloud seats/roles | Clearly call it a solo workspace until team permissions exist |
| What does white-label mean? | Pricing shorthand can imply a branded hosted portal | Spell out output-only branding versus domain/app/service rebranding rights |
| Can I move between Desktop and Cloud? | They are separate products; no demonstrated seamless sync | Portable import/export schema before promising sync |
| What if generation or download fails? | Some recovery is technical; image status is lost | User-facing job state, component retry and support reference ID |
| Will this outperform my current process? | Samples are disclosed but not a measured productivity benchmark | Pilot studies measuring editing time and usable packs, not invented ROI |

### The three highest-value product additions

1. **Structured campaign editor plus free visual re-render.** This improves the value of every existing feature.
2. **First-class image lifecycle.** Consent, provider status, cost cap, private asset storage, crop/format handling and targeted retries.
3. **Client review and approval in Cloud.** This makes the agency proposition meaningfully stronger than a bundle of generators.

Avoid prioritizing autonomous posting, more provider logos, more “agents,” or a massive template catalog before these basics work reliably.

## 7. Business model and positioning

### A more defensible initial customer

My suggested initial segment is **solo marketers and small agencies producing repeat campaigns for local/service businesses**, especially where English/Urdu/Hindi output and reusable client brand context are useful. This is a hypothesis to test, not established market demand.

Suggested positioning:

> Turn a client brief into a branded campaign pack you can review, revise and hand over.

Supporting message:

> Copy, visuals and portable source files in one repeatable workflow. Start in Cloud; choose Desktop when local ownership matters.

Do not try to win simultaneously as a Canva replacement, autonomous agency, SEO auditor, enterprise governance platform and source-code resale business. Those are different purchases with different support and trust requirements.

### Pricing and unit economics

At full allowance utilization, headline revenue per included campaign is:

| Plan | Arithmetic | Gross revenue per included campaign |
|---|---:|---:|
| Pro monthly | $49 / 50 | **$0.98** |
| Pro annual | $490 / (12 × 50) | **about $0.817** |
| Agency monthly | $99 / 300 | **$0.33** |

These are not profit numbers. They exclude payment processing, taxes where applicable, refunds, hosting, storage, text/image calls, retries, support and acquisition.

A simple sensitivity test illustrates why F02 matters: **at a hypothetical $0.10 image cost**, 300 image campaigns cost $30 before every other expense; **at a hypothetical $0.30**, they cost $90. These are scenarios, not quoted provider prices. Measure actual configured provider/model costs before deciding that 300 image-enhanced packs for $99 is sustainable.

Consider separate transparent image allowances or credits if image costs vary substantially. Do not hide them inside an ambiguous “campaign” allowance. BYOK should lower text cost but must not accidentally bypass image accounting.

### Desktop economics

$199/$499 one-time revenue is compatible with local ownership, but Python setup, 24-month maintenance and Source onboarding can consume margin. Establish a support reserve, clear supported platforms and a repeatable installer. Define what happens after the included maintenance period before the first paid cohort arrives.

The $499 source/resale audience is not the same as a small business buying a campaign tool. Give it a separate sales path, operating-cost calculator and licensing explanation. Source availability is not the same as open-source rights; the proprietary notice already communicates this reasonably clearly.

### Conversion and trust improvements

- Separate Cloud and Desktop purchasing decisions early, without forcing a feature-matrix study.
- Keep the fictional sample labels; they build credibility.
- Show a live, consented end-to-end creation/edit/export recording alongside the illustrated tour, clearly distinguishing the two.
- Provide seller/entity identity, contact route, support hours, refund process and renewal terms consistently. The license still calls itself a prelaunch candidate; obtain appropriate legal review before charging.
- Publish an understandable provider/data-processing list, retention practices and deletion behavior. Do not imply “securely stored” means end-to-end encryption.
- Define priority support in practical terms rather than an undefined adjective.
- Add privacy-conscious funnel events. The shipped analytics provider is empty, so there is no configured client analytics integration in that config; server logs alone do not tell the full acquisition story.

### Metrics that matter

Measure landing → signup → confirmed email → first saved campaign → first export → second campaign → paid conversion. Add time to first usable pack, minutes spent editing, template-fallback rate, image-failure rate, export failures, cost per usable pack, support tickets per active customer and refunds by cause.

A useful north-star candidate is **weekly reviewed-and-exported campaign packs per active customer**, not total generated text or total accounts.

## 8. Implementation roadmap

### Phase A — contain paid-feature risks

**Engineering:** F01–F06. Add no-AI enforcement, image monetary reservations, persisted image status, provider-specific contracts, correct provenance and payload-safe asset delivery.

**Product/design:** Correct availability wording and the two contrast failures. Make the hero-only image limitation explicit until resolved.

**Release:** Keep checkout gates closed for unverified flows. Establish staging accounts and test provider budgets rather than experimenting on customer data.

### Phase B — complete the customer journey

- First-campaign guided brief and practice sample.
- Structured visual copy editor with free deterministic rerender.
- Image-only retry and clear fallback/allowance policy.
- Fast durable fulfillment recovery and alerts.
- CI real-browser gate, with failure artifacts.
- Consistent artifact versioning and tested Desktop setup instructions.

### Phase C — validate willingness to pay

Recruit a small pilot cohort in one segment. Observe users completing a real pack without coaching. Measure time saved against their current process and ask what they would actually pay. Validate the local-first and source-resale propositions with separate cohorts rather than averaging them together.

Only then expand into Cloud review links, team roles, product-photo workflows or additional integrations.

## 9. Paid-launch acceptance checklist

- [ ] Real signup, confirmation, login, logout and password recovery on staging.
- [ ] Two-user isolation tests against deployed RLS and all data endpoints.
- [ ] No-AI mode makes no model-provider calls; provider disclosures match reality.
- [ ] Text plus image reservations respect total monetary budgets under concurrency.
- [ ] Each enabled provider passes a real request/response smoke test with a spend cap.
- [ ] Image status/provenance survives save, reload, edits and export.
- [ ] Maximum-size campaigns remain retrievable through deployed infrastructure.
- [ ] Edited copy and visuals cannot silently diverge in a final pack.
- [ ] Checkout, upgrade/downgrade, annual billing, cancellation, failed payment, refund and duplicate/out-of-order webhook cases are exercised end-to-end.
- [ ] Account deletion cancels verified subscriptions and remains recoverable when a provider is down.
- [ ] Desktop purchase → email → private download → checksum → fresh install succeeds.
- [ ] Delivery backlog recovers within a stated service target.
- [ ] Fresh Windows/macOS/Linux installs match the advertised support matrix.
- [ ] Light/dark browser checks pass, plus manual keyboard/zoom/mobile export checks.
- [ ] Backup restore is proven; alerts and support ownership are assigned.
- [ ] Seller/license/privacy/refund terms are approved for the actual launch markets.

## 10. Evidence and source map

Local evidence is included in the audit package. Provider keys used in reproductions were fake; the public config response contains only the normal public Supabase anon key.

| Evidence file | Contents |
|---|---|
| `evidence/live-api.json` | Read-only live endpoint statuses and headers |
| `evidence/deploy-parity.json` | Live/source hashes for five selected frontend files |
| `evidence/link-check.json` | 49 sampled internal URL/asset checks |
| `evidence/browser-results.json` | Six live dark/default browser checks |
| `evidence/live-light-theme.json` | Live light-theme contrast findings |
| `evidence/local-reproductions.json` | Offline/image request, budget and payload-size reproductions |
| `evidence/openai-contract.json` | Fresh-process OpenAI request and provenance reproduction |
| `evidence/db-reproduction.json` | Actual schema drops visual status on save |
| `evidence/fixture-browser.log` | Repository harness summary and failing exit |
| `fixture-qa/browser-verification.json` | All 97 fixture/static browser result records |
| `evidence/manifest-check.json` | Release manifest comparison, with build caveat above |
| `evidence/*png` | Live screenshots, including light theme |

### Source references at the audited commit

Use these immutable links rather than moving `main` when implementing fixes:

- [Campaign route](https://github.com/nabsan144-hub/brandforge-os/blob/5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b/cloud/api/_lib/routes/campaigns.js)
- [Cloud engine](https://github.com/nabsan144-hub/brandforge-os/blob/5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b/cloud/api/_lib/engine.js)
- [Image providers](https://github.com/nabsan144-hub/brandforge-os/blob/5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b/cloud/api/_lib/visuals_ai.js)
- [Cost guard](https://github.com/nabsan144-hub/brandforge-os/blob/5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b/cloud/api/_lib/cost.js)
- [Generation migration](https://github.com/nabsan144-hub/brandforge-os/blob/5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b/supabase/migrations/0007_generation_ledger.sql)
- [Cloud browser app](https://github.com/nabsan144-hub/brandforge-os/blob/5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b/cloud/public/app.js)
- [CI workflow](https://github.com/nabsan144-hub/brandforge-os/blob/5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b/.github/workflows/ci.yml)
- [Desktop local security](https://github.com/nabsan144-hub/brandforge-os/blob/5f73af85137c3b1e9d5d23d9d7f3bf5a2decd83b/app/modules/local_security.py)

**Bottom line:** Preserve the solid groundwork. Finish the image lifecycle and the edit-to-export workflow, make today’s availability unmistakable, and prove the paid customer journey before increasing acquisition spend.
