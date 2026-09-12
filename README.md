> Current complete source delivery: [1.14.0 scope and evidence](DELIVERY-1.14.0.md). Start with the [owner/staging handoff](OWNER-HANDOFF-1.14.md) and [Windows GitHub commands](PUSH-WINDOWS-CMD.txt). Earlier versioned handoffs are historical.

# BrandForge OS

> **Current handoff: 1.12.0 complete source candidate.** See [delivery summary](DELIVERY-1.12.0.md), [exact fixes and remaining gaps](docs/audit/FOLLOW-UP-1.12.0.md), [all 91 statuses](docs/audit/91-ITEM-RECONCILIATION.md) and [owner instructions](docs/audit/OWNER-HANDOFF.md). Not production approval or completion of all acceptance criteria.

> **Historical 1.4.2 runtime-audit revision:** the Source edition includes the integrated website/video/HTML tour, the supported Cloud backend and the full Desktop project. The Owner archive is a focused Desktop runtime with customer documentation, not operator runbooks. See [audit log](docs/FULL-AUDIT.md) and [owner setup/deployment guide](docs/OWNER-GUIDE.md) and [runtime verification follow-up](docs/RUNTIME-AUDIT-1.4.2.md). Live payment, delivery, platform and legal sign-off remain separate owner tasks.


A reviewable campaign workspace with two **separate** products:

- **Desktop:** local ownership. Owner $199 once; Agency + Source $499 once. Offline templates after setup, optional connected providers, client profiles, revision/approval workflows and portable/native exports.
- **Cloud:** hosted browser workspace. Free 3 lifetime campaigns; Pro $49/month or $490/year with 50/month; Agency $99/month with 300/month. Three text stages, deterministic vectors, saved brands, editable copy and exports. Not the identical Desktop pipeline.

**Billing gate:** Cloud checkout code ships in this repository, but production billing stays disabled until the operator passes the release gate (BILLING_RELEASE_VERIFIED, plus the checklist in OWNER_LAUNCH_TO_DO.md: legal terms approval, live provider + email verification, sandbox-to-live billing test). Local tests alone do not verify live billing, email or provider output quality. The source is proprietary and published for inspection/evaluation, not open source.

## Start / operate

- [Desktop installation, offline launch and repair](START-HERE.md)
- [Canonical Cloud/payment/fulfillment launch runbook](docs/LAUNCH-RUNBOOK.md)
- [Plain-English rights and product matrix](docs/RIGHTS-MATRIX.md)
- [Implemented capabilities and external release gates](docs/PRODUCT-ACCEPTANCE.md)
- [Network/privacy boundaries](docs/NETWORK-PRIVACY.md)
- [Security reporting](SECURITY.md)

Owner archives intentionally omit Cloud/development source. Use `START-HERE.md` inside a customer archive.

## Repository map (Source / development checkout)

`app/` is the local Python/FastAPI runtime and compiled Svelte dashboard. `cloud/` plus `supabase/` is the operated hosted product. `sales/` is marketing and client-side preflight tools. The obsolete second Cloud prototype has been retired; do not deploy older Docker/Fly/Railway recipes.

Use the canonical guide rather than old commands referring to nonexistent modules or Paddle Classic downloads. See `CHANGELOG.md` for intentional output/plan/test-contract changes in 1.4.
