# Phase 5A — Copy/visual review and export safeguards

**Implemented locally. Not pushed, deployed or applied to a live database.**

Branch: `fix/phase-5-visual-review` · Baseline: Phase 4 `12e1be3860261735004ee21d7e13220c9adb3558`.

> Subsequent work: [Phase 5B](PHASE-5B.md) adds gated corrections and exact version restore for new inline vectors only. The scope statements below describe Phase 5A at delivery, not the newer implementation.

## Scope: an interim safeguard, not completed synchronization

This batch addresses the immediate T10 risk: editing campaign copy must not silently produce an export that pairs new copy with old artwork.

**It does not yet implement canonical editable headline/offer/price/CTA/destination fields or no-charge visual re-rendering.** The existing files remain unchanged. T10 stays **partial** until those features, their version handling and staging evidence are complete.

## Implemented behavior

| Situation | Behavior |
|---|---|
| Newly generated campaign | `unchanged` means the visuals have not been marked stale by a later copy edit. It is not an accuracy or layout certification. |
| Existing campaign at migration | Alignment becomes `unknown`, rather than assuming historical files match current text. |
| Copy actually changes | SQL marks the visuals `review_required`, retains their exact bytes and creates the existing text revision. |
| No-op copy edit / strategy / SEO / rename | Does not newly mark otherwise unchanged visuals stale. Any new revision invalidates a previous acknowledgment on an already flagged campaign. |
| Open flagged campaign | Owner can read the copy and preview the original visuals. A persistent notice says they have **not** been redrawn. |
| ZIP, source, PNG or JPEG download | The shipped UI requires acknowledgment of the exact current version before proceeding. The ZIP builder independently checks review state. |
| Acknowledge | Explicit confirmation, owner authorization and optimistic revision check. It does not change files, consume a campaign allowance, call an AI provider or create another text revision. Repeating a successful acknowledgment is idempotent. |
| Edit after acknowledgment | Old acknowledgment is invalidated; it cannot silently approve a newer version. |
| Restore text | Creates a new version using existing restore semantics. Changed copy requires fresh review; old snapshot acknowledgments are never restored as current approval. Visuals remain unchanged. |
| Account-data export | Remains available without declaring visuals correct. Unreviewed campaigns trigger a separate archive confirmation. The JSON preserves files, review state and affected IDs/revisions; it is labeled an archive, not a publish-ready pack. |
| Old browser tab | Newly fetched flagged detail, private assets and account-export pages require the review-aware client header, producing a controlled reload message for older clients. |

### Persistence and ownership

Migration **0014_visual_review.sql** adds review state, acknowledged revision and timestamp. It replaces `edit_campaign` while preserving owner checks, optimistic revisions, stage provenance and the last-ten-text-version retention. A service-role-only `acknowledge_visual_review` RPC locks the current row, checks the owner and exact revision, and records only the acknowledgment. Missing expected revisions fail closed.

Clients cannot set these fields through ordinary edit payloads. Other accounts cannot acknowledge a campaign. The acknowledgment remains a user's explicit acceptance of possible differences—not a claim that BrandForge verified matching words.

### Export disclosure and provenance

ZIP files include **COPY-VISUAL-REVIEW.txt**, alongside campaign metadata and the existing publishing checklist. The note retains the reason for review and the acknowledged version/time; it never pretends that acknowledgment regenerated artwork.

Human copy edits now display **“copy: edited (you)”** instead of being mislabeled as AI merely because their provider was not `offline`.

The original Free watermark, customer logo bytes and private bundle hashes remain unchanged. No new image generation or watermark rewriting is introduced.

## Important limits

- This is workflow protection, **not DRM or a security restriction on an owner's own files**. Previewing SVG/images necessarily exposes their bytes to that owner. A technically capable owner can save a preview or use another client. The safeguard prevents unnoticed mismatch in supported export flows; it does not make unacknowledged files impossible to extract.
- Already downloaded files and already loaded historical snapshots cannot be recalled. Version metadata identifies what was exported; it does not guarantee that it is the latest state in another tab.
- Acknowledgment is not automated proofreading, legal approval, brand approval, proof of correct pricing or permission to publish a misleading claim.
- A general strategy/SEO edit is not analyzed for semantic effects on artwork. Canonical visual fields and explicit dependencies remain follow-on work.
- Historical alignment is intentionally unknown. This can add a review step for old campaigns even if their files happen to match.
- Account portability does not force users to approve inaccurate visuals. Archive confirmation does not write a campaign acknowledgment.

## Verification

- **296 Cloud tests across 31 files passed.**
- **16 new visual-review tests** cover copy edits, non-copy/no-op behavior, unknown history, ownership, revision conflicts, null revisions, idempotent acknowledgment, restore, invalidation, forged fields, old clients, archive portability and browser export predicates.
- Database tests run the real migrations and RPCs in PGlite. Upgrade coverage verifies that pre-migration rows become `unknown` while new rows default to `unchanged`.
- **Four actual Cloud UI browser flows**: dark/light × 390/1440px, using shipped JavaScript and CSP. Edit → stale notice → blocked ZIP/source/PNG → archive cancel/accept without campaign approval → review cancel/accept → successful ZIP. Exact original SVG bytes, review note and every ZIP SHA-256 are checked. Zero axe violations, overflow or page errors.
- Existing **eight consent/accessibility states** passed again.
- Existing **18 PNG/JPEG watermark checks and ZIP hashes** passed again.
- Existing private-bundle browser proof passed again: five files, **ten PNG/JPEG watermark checks**, verified ZIP and portable JSON, no leaked signed URLs or storage credentials.
- Syntax, schema synchronization and whitespace checks passed.

The new UI uses offline API fixtures; real SQL semantics are verified separately. No real account, storage service, paid provider, checkout, live migration or production endpoint was exercised. Sales source did not change in this batch. Remote CI remains unverified; the new browser flow is added to the existing Cloud browser CI job.

Evidence: `docs/implementation/evidence/phase-5-*`, `scripts/visual_review_qa.py`, and the updated existing browser harnesses. Their freshly generated synthetic packs explicitly identify themselves as unchanged since generation; missing review metadata does not silently bypass the ZIP guard.

## Staging rollout requirements

1. Back up staging data. Apply migration **0014 after 0013**, and deploy the matching API, `app.js`, `visual-review.js`, HTML and export tools in a coordinated maintenance window. Do not leave the old API/UI active after adding review state: old code does not understand it. A generation-only pause is not a general edit freeze.
2. Test old browser tabs, cache invalidation and controlled reload errors. Verify that the public browser roles cannot call the acknowledgment RPC directly or write campaign review columns.
3. Test new and historical campaigns, both inline and private bundles, across copy edits, restore, review, replay and another-tab revision conflicts. Confirm previews remain usable before review; otherwise users cannot reasonably acknowledge them.
4. Verify ZIP, source, PNG/JPEG and account-archive cancellation/acceptance on real staging desktop/mobile browsers. Check that archive export preserves all data without writing approval. Confirm the exact revision and warning survive download.
5. Verify no generation, image-provider, quota, billing or asset mutation occurs during edits/acknowledgments. Existing request safety rate limits still apply.
6. Preserve Phase 3 private-storage security, cleanup and rollback requirements. This migration adds no bucket or provider permission and does not replace those open gates.

### Rollback

There is no automatic “approve everything” or “mark all historical rows unchanged” fallback. Retain the review-aware API/client and review metadata while addressing issues. Do not drop the new fields or restore the old unguarded exporter after copy edits have occurred. Account archives and the operator legacy recovery tool remain distinct recovery paths, not publishing approval.

## Remaining work

T10 remains partial: canonical visual fields, explicit dependency tracking, no-charge deterministic re-rendering, AI-scene preservation, version-consistent visual restore, and revision-safe private bundle replacement/cleanup still need implementation and verification. This batch intentionally does not change those files or build a partial renderer that could lose artwork or remove a watermark.

All **91 tracked items** (original 90 plus W01) remain in `PROGRESS.csv`. No other creative, billing, Desktop, deployment, key-validation or recovery task is silently marked complete. The `bfos/` duplicate remains untouched. **Nothing was pushed, deployed, charged or enabled.**
