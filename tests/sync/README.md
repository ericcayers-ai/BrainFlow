# Sync test fixtures

Conflict and recovery fixtures for `brainflow-sync`.

| Fixture | Purpose |
|---------|---------|
| `fixtures/markdown_conflict/` | Divergent Markdown block edits (AC-SYNC-03) |
| `fixtures/workflow_conflict/` | Same node `id` edited on both sides |
| `fixtures/rename_delete/` | Markdown emptied remote + JSON delete-vs-edit |
| `fixtures/interrupt_mid_push/` | Durable journal simulating mid-push kill (AC-SYNC-01) |
| `fixtures/offline_queue/` | Seed queue for drain / idempotent enqueue (AC-SYNC-05) |
| `fixtures/three_device/` | 3-way simultaneous Markdown + JSON pairwise merges |
| `fixtures/clock_skew/` | Divergent content with skewed `authored_at` metadata |
| `fixtures/token_expiry/` | Unauthenticated status + offline queue preserved |
| `fixtures/default_branch_changed/` | Remote default branch mismatch; force forbidden |

Run:

```bash
cargo test -p brainflow-sync
cargo test -p brainflow-sync --test conflict_fixtures
```

Interrupted mid-push recovery is covered by unit tests in `recovery` plus the journal fixture (AC-SYNC-01).
Force-push rejection is covered by `git::tests::never_allows_force` (AC-SYNC-02).
Offline queue idempotency/drain: `queue` unit tests + offline_queue fixture.
Live multi-device soak remains a beta gate — see [docs/GITHUB_SYNC.md](../../docs/GITHUB_SYNC.md) §9.

### Dry-run simulation

```bash
cargo test -p brainflow-sync --test multi_device_dry_run
```

Chains 3-device pairwise merges, clock skew, interrupt recovery, queue drain, and token/branch contracts without GitHub accounts. Manual live matrix is documented in GITHUB_SYNC.md §9.
