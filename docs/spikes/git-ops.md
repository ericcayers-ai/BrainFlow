# Spike: Git ops (align ADR 0005)

**ADR:** [0005-git-strategy.md](../adr/0005-git-strategy.md)

## Options compared

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| gitoxide (`gix`) | Pure Rust, modern, embeddable | Some porcelain still maturing | **Primary** |
| libgit2 (`git2`) | Battle-tested merge/index | C dep, safety surface | Escape hatch |
| `git` subprocess | Completeness | Harder to sandbox; easy to misuse from UI/AI | State-machine only, never AI tool |

## Decision

Implement Sync as an embedded state machine in `crates/sync`. Foundation slice ships a stub (`SyncState` enum + `force_push_forbidden`). No automatic force-push. Credentials stay in OS keychain (future).

## Unresolved

Multi-device soak and org SSO live drills remain beta gates. Core conflict matrix, LFS docs (opt-in), and interrupt recovery are covered under github-sync (`crates/sync`, `tests/sync`).
