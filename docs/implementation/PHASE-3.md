# Phase 3 — Private campaign files and lifecycle

**Implemented and verified locally. Not pushed, deployed or enabled.**

Branch: `fix/phase-3-private-assets` · Based on Phase 2 commit `528cc1c2db356dddaed6a81ce3e7de14c5f3f2a1`.

## What changed

| Area | Local implementation |
|---|---|
| Storage | One immutable private JSON bundle per new campaign, rather than large generated-file strings in campaign JSON. Metadata retains a file manifest and bundle ID. |
| Limits | 20,000,000 bytes per serialized bundle; 8,000,000 decoded bytes per file; at most 64 files. The existing 3MB campaign metadata/inline save guard and 4MB web-response guards remain. Existing tighter image-provider limits remain unchanged. |
| Atomic save | A durable pending row is written **before** upload. SQL validates the owner, generation, confirmed upload, manifest and pending state; attaching the bundle, inserting the campaign and committing its allowance happen in one transaction. |
| Failure/replay | Upload/save failure does not consume a campaign allowance. A lost completion response cannot refund a committed campaign or delete its files. Completed-request replay does not upload again. Provider budget reservations remain conservative, as in Phase 1. |
| Access | `GET /api/campaigns/:id/assets` checks the signed-in owner and attached bundle, rechecks bucket privacy, rate-limits delivery and returns a 60-second signed URL with size/hash. No large file is proxied through Vercel. Responses are no-store. |
| Browser | The browser accepts only the configured HTTPS Supabase origin, disallows redirects, sends no credentials/referrer to storage, bounds streamed bytes, and verifies bundle and per-file SHA-256 plus the manifest before exposing files. Signed URLs are not persisted in exports. |
| Portability | Existing previews, individual downloads, rasterization and ZIP receive the verified original file structures. Account export hydrates every campaign on its bounded page before download. Any missing/corrupt/expired file fails the operation rather than producing an empty export. |
| Stale clients | New creates when enabled, private campaign detail and private account-export pages require `X-Brandforge-Client: asset-bundle-v1`. Old tabs receive a controlled reload error. Completed generation replays remain recoverable. |
| Deletion | Bundle rows survive campaign/account cascades. Maintenance claims detached bundles and pending uploads older than 24 hours, removes objects, then deletes rows with a matching 15-minute lease token. Failed operations retry after lease expiry. Fresh/attached bundles cannot be claimed for deletion. |
| Operations | Cleanup handles 25 bundles per maintenance call; failures and a full batch produce alerts. The existing scheduler is daily, not instant deletion. Operators must drain full batches and monitor backlog; no immediate-erasure SLA is claimed. |
| Legacy | An operator-only, read-only-by-default CLI converts one explicitly selected owner/campaign. Revision-checked attachment refuses concurrent edits. Oversized legacy rows can instead be recovered to an exclusive-create, mode-0600 JSON file outside Vercel. No historical rows were migrated here. |

The Free watermark remains **embedded in the actual file bytes**. Moving files does not alter attribution, paid outputs, uploaded customer logos, or historical work. No AI key was requested or changed; Free image generation stays off.

## Verification

- Full Cloud suite: **272 tests across 29 files passed**.
- New private-file suite: **19 tests**, real PGlite migrations/RPCs and fake object storage, including mismatched ownership/generation, upload failure, uncertain save, quota preservation, replay, role grants, deletion cascades, lease retries, cross-owner denial, stale clients, corrupt downloads, portability, revision conflict and oversized recovery.
- Offline Chromium private-bundle test uses the **actual backend encoder and shipped browser functions**: five Free SVGs, ten PNG/JPEG watermark checks, ZIP source/hash verification and portable account JSON all passed. Storage requests sent no authorization, cookie or referrer. Missing, expired and corrupt files were rejected. Zero page errors.
- Existing watermark regression: **18 PNG/JPEG checks and ZIP hashes passed**.
- Existing consent/accessibility regression: **8 UI states passed**, zero axe violations, overflow or page errors.
- JavaScript syntax, migration/schema synchronization and whitespace checks passed.

Evidence: `docs/implementation/evidence/phase-3-*.{log,json}`. The offline browser harness is also added to CI; remote CI was not run here.

**These are not live Supabase, Vercel latency, paid-provider, or production recovery proofs.**

## Staged rollout — do not skip these gates

1. Back up staging DB/storage and record the deployed commit. Apply `supabase/migrations/0013_private_campaign_assets.sql` after 0012. Use migrations, not a blanket replacement of production schema.
2. Create a dedicated **private** bucket. Allow JSON objects up to at least 20,000,000 bytes. Do not add browser read/write policies for these objects. Review **all existing `storage.objects` policies**, including policies that match every bucket; `public=false` alone does not neutralize overly broad authenticated policies.
3. Confirm anon and a different authenticated account cannot list, upload, download, update, or remove these objects through the Storage API. Confirm `campaign_asset_bundles` and its RPCs are service-role-only. Service-owned uploads must not block account deletion.
4. Deploy the new API, reader, export tools and maintenance **together with the flag still false**. Set `CAMPAIGN_ASSET_BUCKET` through deployment configuration. Never expose the service-role key to the browser or paste it into a report.
5. Verify CORS from the real app origin, signed URL origin and expiry, CSP, MIME/file-size restrictions, storage bytes/hash, and bucket privacy failure. Current CSP allows `*.supabase.co`; a custom Supabase domain requires an explicit reviewed CSP change, not a wildcard relaxation.
6. Enable `CAMPAIGN_ASSETS_ENABLED=true` **in staging only**. Generate Free vector packs first; test preview, individual files, PNG/JPEG, ZIP and all account-export pages on desktop and a low-memory mobile browser. Exercise stale tabs, session expiry and a mid-download deletion. Signed links are bearer capabilities valid for up to 60 seconds; do not log them.
7. Prove upload/save faults, lost response replay and reservation expiry with actual storage/network failures. Measure the full operation under Vercel's existing 60-second configuration. End-to-end deadline work (O02) is still open; do not assume the new upload fits every paid generation.
8. Delete a staging campaign and a staging account; run authorized maintenance and verify actual objects disappear. Simulate a failed removal and retry after lease expiry. Drain full 25-item batches. The repository cron is once per day; higher-volume operation needs a monitored supported schedule or an operator drain procedure before promising a deletion deadline.
9. Export a legacy staging campaign to a protected recovery file, verify its exact file bytes, then dry-run and explicitly apply its conversion. Prove recovery and restore against a real project backup separately; the CLI is not a complete backup system. Retain the source until verified. Never put customer recovery files in Git or the handoff ZIP.
10. Record every result before enabling production private assets. Paid imagery, model access/pricing and checkout gates are separate; none was enabled by this phase.

### Legacy operator commands

Supply `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and (for apply) `CAMPAIGN_ASSET_BUCKET` securely in the operator environment. Run from the canonical repository root with Cloud dependencies installed.

```sh
# Read-only size/hash/revision assessment; uploads nothing.
node cloud/scripts/migrate-private-assets.mjs --owner OWNER_UUID --campaign CAMPAIGN_UUID

# Recover an inline row even when it exceeds the supported web/bundle size.
# Writes private customer data: use an encrypted operator disk and a NEW filename.
node cloud/scripts/migrate-private-assets.mjs --owner OWNER_UUID --campaign CAMPAIGN_UUID --recover /secure/new-recovery.json

# Explicitly convert only the selected campaign after recovery verification.
node cloud/scripts/migrate-private-assets.mjs --owner OWNER_UUID --campaign CAMPAIGN_UUID --apply
```

A revision conflict leaves the original inline row/edits untouched and the unused pending bundle eligible for later cleanup. Oversized/unsupported bundles fail closed; recovery is still available. Already-private campaigns use the authenticated workspace export, not this inline recovery mode. This is deliberately not an unattended bulk migration.

### Rollback

Set `CAMPAIGN_ASSETS_ENABLED=false` to stop **new** private uploads. Keep migration 0013, the private reader, signing endpoint and maintenance deployed so existing private campaigns remain usable. New inline packs still face the Phase 2 save cap. Do not roll back to the old frontend/API or drop the bundle table/bucket after private campaigns exist. Re-inlining/fully reversing this migration needs a separate verified recovery procedure; none is executed automatically.

## Still open — honest boundaries

- T03 remains **partial**, not launch-certified: image decode/normalization, live storage/security/latency checks and maximum real-provider output proof remain open.
- O03 now has local cleanup and alerts, not a completed retention policy, lifecycle SLA, backlog capacity proof or backup-restoration drill.
- Local SQL tests exercise lease state transitions; they do not replace real concurrent Supabase workers or outage testing.
- CLI recovery/conversion logic is locally tested; the full operator flow against a real legacy project remains a release gate.
- A bundle download currently loads all campaign files; memory/egress costs must be validated on target mobile devices.
- Prior consent, provider-budget, payload, creative-quality, marketing, billing, Desktop and operational items remain tracked. No design overhaul is implied by storage work.
- `bfos/` is still an untouched duplicate; no synchronization, deletion or recertification was performed.

The authoritative master plan remains all original 90 items plus W01. See `PROGRESS.csv` for each item; this phase does not close unrelated work or imply that no undiscovered defects exist.
