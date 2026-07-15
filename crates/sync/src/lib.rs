//! Git sync state machine for BrainFlow vaults.
//!
//! # Non-negotiables
//! - Sync is a **dedicated state machine**, not hidden shell commands.
//! - Sync is **never** an AI / planner tool ([docs/GITHUB_SYNC.md](../../docs/GITHUB_SYNC.md)).
//! - Credentials live in the **OS credential store**, never the vault.
//! - **Never** automatic force-push (AC-SYNC-02).
//!
//! # Git strategy (ADR 0005)
//! gitoxide (`gix`) for discovery/integrity; libgit2 for porcelain escape hatch.

mod auth;
mod credentials;
mod git;
mod gitignore;
mod merge;
mod preflight;
mod queue;
mod recovery;
mod state;
mod validate;

pub use auth::{
    auth_status, begin_device_flow, logout, poll_device_flow, set_personal_access_token,
    AuthError, AuthStatus, CreateRepoRequest, DeviceCodeResponse, RemoteRepo,
};
pub use credentials::{has_token, redact_token, AuthMethod};
pub use git::{
    force_push_forbidden, force_push_invocation_count, gix_discover, gix_integrity_ok, ConflictItem,
    ConflictKind,
};
pub use gitignore::{ensure_brainflow_gitignore, BRAINFLOW_GITIGNORE};
pub use merge::{merge_json_by_stable_ids, merge_markdown_three_way, JsonMergeOutcome, MergeOutcome};
pub use preflight::{
    large_file_notes, scan_paths, secrets_block_commit, LargeFileNote, PreflightKind,
    PreflightWarning,
};
pub use queue::{drain_queue, enqueue, HistoryEvent, QueuedCommit};
pub use recovery::{recover_from_interrupt, InterruptedOp, SyncJournal};
pub use state::{
    ConflictResolution, SyncEngine, SyncError, SyncSettings, SyncState, SyncStatus,
};
pub use validate::{validate_vault_workflows, ValidateReport};

/// Capability gate: LLM / worker must not receive Git verbs.
pub fn is_ai_tool() -> bool {
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sync_is_not_an_ai_tool() {
        assert!(!is_ai_tool());
        assert!(force_push_forbidden());
    }
}
