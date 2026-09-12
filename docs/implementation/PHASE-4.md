# Phase 4 — Truthful availability and sales-page contrast

**Implemented and tested locally. Not pushed, deployed or enabled.**

Branch: `fix/phase-4-availability-contrast` · Baseline: Phase 3 `2732e7dca90cf0e03c0524b97562dc8d9d05794b`.

## T07 — both reported contrast defects fixed

- Homepage: the Desktop setup terminal remains a dark surface in either theme. Its small header now uses a surface-specific inverse color instead of inheriting the light-theme muted text color.
- Pricing: the Desktop-alternative note now uses opaque muted text rather than `text-muted/80`.
- Actual Chromium light-theme measurements at **390px and 1440px**: terminal header **8.52:1**, pricing note **6.00:1**. Both exceed the 4.5:1 normal-text minimum. The prior audit recorded 3.07:1 and 3.83:1 respectively.
- Dark-theme checks pass too: 9.03:1 and 6.96:1.
- Homepage and pricing were scanned with collapsed details opened and scroll-reveal content visible. Zero WCAG A/AA axe violations, horizontal overflow or page errors in the eight page/theme/width combinations.

This is local rendered-browser evidence, not a claim that the live website has changed or that every other page has been visually recertified.

## T08 — one release-state reader, independent paid products

### Concrete bugs removed

1. The homepage no longer says **“Desktop early access open”** while the public funnel sends customers to a waitlist.
2. Desktop buttons and pricing badges no longer infer live checkout from public price IDs. That could advertise a purchase even when payment actions were gated closed.
3. Cloud buttons no longer probe `/api/billing/paddle-client-token` to decide availability. That endpoint can return a token when **either** product is enabled, so Desktop-only readiness could incorrectly advertise paid Cloud checkout.
4. Pricing's separate inline badge updater and Cloud's separate token-based updater are retired in favor of one shared reader.

### New behavior

- Public `GET /api/capabilities` returns **200 for expected closed checkout**, with separate Cloud and Desktop booleans, the Free allowance, imagery scope/configuration and generation-pause status.
- It sends no credentials, tokens, private storage paths, price IDs or diagnostic environment-variable lists. It is no-store and uses the existing configured-origin CORS policy.
- It reuses the actual backend billing-readiness checks. Public paid checkout is advertised only for an enabled **production** configuration; sandbox testing never becomes a public purchase promise.
- `sales/assets/availability.js` owns the homepage summary, pricing badges/notes, Desktop buttons, and Cloud monthly/annual CTA labels and links. It is included consistently after launch config on the sales pages.
- Desktop public promotion still additionally requires the existing build-time funnel flag. A backend-ready release does not override an intentionally closed storefront.
- On missing, malformed, failed or timed-out capability responses, paid links revert to Free signup and Desktop waitlist language. A four-second abort bounds the status request. Public price metadata cannot override this state.
- Desktop purchase clicks refresh availability before loading the SDK or creating a transaction. The backend still independently validates release gates, catalog prices and private fulfillment artifacts. No authorization was moved into the browser.
- The waitlist remains reachable even when checkout is configured; visitors need not start a purchase to register interest.

**Meaning of this endpoint:** release configuration, not an uptime monitor or a guarantee that a provider will accept a transaction. It does not contact Paddle, validate current remote inventory, or probe live Supabase Auth. Free's three-campaign allowance is an offering description, not proof that signup is operational during an outage. The existing payment endpoints remain fail-closed.

## T09 — hero-only imagery disclosed near the offer

Homepage, pricing comparison, FAQ and relevant structured FAQ text now explain:

- Free campaigns use watermarked vector visuals.
- AI artwork is optional on Pro/Agency, with explicit opt-in and operator availability.
- **AI artwork applies to the hero only; resized banners remain vector-only.**
- A labeled vector fallback that is saved still consumes one campaign.
- Example artwork is not proof that image generation is enabled now.

The public image-configuration indicator additionally requires the image flag/key and a positive, model-bound image-cost estimate. It does not reserve budget or promise provider access. The page retains the static scope disclosure if scripts or the status endpoint fail.

An absolute “headline can never be misspelled” claim was replaced with the accurate distinction: separating typography from image generation preserves supplied text; it does not proofread it. This is a disclosure correction, not a creative-quality overhaul.

## Verification

| Check | Result |
|---|---|
| Full Cloud suite | **280 tests / 30 files passed** |
| New capability tests | **8 passed**, including product separation, production vs sandbox, release/configuration guards, CORS, method handling and no secret fields |
| Sales funnel tests | **37 passed**, including server recheck before Desktop checkout and no stale buy label after failure |
| Sales demo integration | **54 checks passed** |
| Sales structural accessibility | **14 pages passed** in jsdom; this is separate from rendered contrast checks |
| Real Chromium pages | **8 views passed**: homepage/pricing × dark/light × 390/1440px |
| Real Chromium availability | **8 states passed**: closed, Cloud-only, Desktop-only, both, storefront flag off, offline, timeout, malformed response |
| CSS/token guards | Coverage and existing theme/gold/escaped-markup guards passed |
| Static publish build | New reader included; checkout flag remained false; tests excluded from published output |
| Syntax/schema/whitespace | Passed; no database migration added in this phase |

The browser harness loads shipped files with the sales CSP/security headers, supplies offline capability fixtures, blocks external traffic, reveals all expandable/scroll content and runs axe including color contrast. It does **not** contact production or create a payment. Its screenshots and JSON are evidence, not redesigned campaign creatives.

CI now includes this browser gate. **Remote CI has not been run here.** Existing Phase 1–3 regression tests remain part of the passing Cloud suite; their browser harnesses were not rerun in this phase because their shipped Cloud UI/export code did not change.

Evidence: `docs/implementation/evidence/phase-4-*` and `scripts/sales_availability_qa.py`.

## Safe rollout and rollback

1. Keep all checkout/image flags unchanged. Deploy the additive Cloud capability endpoint to **staging** first, then the compatible sales files. A sales deployment reaching an older backend shows safe unverified/waitlist labels rather than enabling checkout.
2. Confirm `BRANDFORGE_MARKETING_URL` and `BRANDFORGE_APP_URL` match real origins, including www/non-www redirects. Check CORS, no-store headers, the static asset cache and the published `hosted_url`.
3. Verify closed checkout returns HTTP 200 capabilities and separate false booleans, while payment actions still reject requests. Use the offline capability fixtures to exercise each enabled-label combination; do not place production credentials in staging or open payment gates just to change a badge. The public UI intentionally does not promote sandbox checkout. Real sandbox payment-flow tests remain separate release work.
4. Confirm the actual deployed homepage/pricing in both themes and widths, expanded details, annual and monthly CTA destinations, waitlist submission, and blocked/slow capability requests. Local fixtures do not prove these deployment paths.
5. For any future paid launch, complete the separate catalog/fulfillment/security/recovery gates before enabling backend and storefront flags. A successful capability response is not a replacement for those gates.
6. Safe rollback is to leave checkout closed and retain the additive endpoint/reader. Do not restore old “open” copy or token-based inference. The Phase 3 rollback rule still applies: never remove its private-file reader/cleanup after private campaigns exist.

No production configuration, Gemini key, paid-provider call, live customer data or deployment was changed. No real bucket or migration operation was performed. The duplicate `bfos/` source remains untouched.

## Plan status and next work

T07 and T08 are implemented with local evidence, pending live/staging verification. T09's disclosure option is implemented for the affected offer/format descriptions, pending release verification. T11 remains partial: local Cloud and sales browser gates exist, but remote CI, full Desktop browser coverage and deployment journeys remain open.

The complete **91-item tracker** (original 90 plus W01 watermark) remains intact. This batch does not close T03's storage/image staging gates, T10's copy/visual synchronization, the creative-quality work, or the remaining billing, Desktop, support and recovery tasks. A natural next batch is **canonical editable visual fields, stale-export protection and safe re-rendering without a full campaign charge (T10)**.
