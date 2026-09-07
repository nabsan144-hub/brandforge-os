# BrandForge OS

> **1.4.2 runtime-audit revision:** the Source edition includes the integrated website/video/HTML tour, the supported Cloud backend and the full Desktop project. The Owner archive is a focused Desktop runtime with customer documentation, not operator runbooks. See [audit log](docs/FULL-AUDIT.md) and [owner setup/deployment guide](docs/OWNER-GUIDE.md) and [runtime verification follow-up](docs/RUNTIME-AUDIT-1.4.2.md). Live payment, delivery, platform and legal sign-off remain separate owner tasks.


A reviewable campaign workspace with two **separate** products:

- **Desktop:** local ownership. Owner $199 once; Agency + Source $499 once. Offline templates after setup, optional connected providers, client profiles, revision/approval workflows and portable/native exports.
- **Cloud:** hosted browser workspace. Free 3 lifetime campaigns; Pro $49/month or $490/year with 50/month; Agency $99/month with 300/month. Three text stages, deterministic vectors, saved brands, editable copy and exports. Not the identical Desktop pipeline.

**Prelaunch implementation:** checkout is deliberately gated. Local tests do not mean live billing, email, legal terms, provider output quality or every OS has been verified. The source is proprietary and published for inspection/evaluation, not open source.

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
