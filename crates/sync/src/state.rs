//! Per-vault sync state machine (see docs/GITHUB_SYNC.md).
//!
//! Sync is **not** an AI capability — LLM/worker tools must never invoke Git.

use crate::auth::{self, AuthStatus, CreateRepoRequest, RemoteRepo};
use crate::git::{self, ConflictItem, IntegrateResult};
use crate::gitignore;
use crate::preflight::{self, PreflightWarning};
use crate::queue::{self, HistoryEvent, QueuedCommit};
use crate::recovery::{
    self, InterruptedOp, SyncJournal,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::time::Duration;
use thiserror::Error;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SyncState {
    Unconfigured,
    Authenticating,
    ReadyLocal,
    Idle,
    Debouncing,
    LockedSnapshot,
    Committing,
    Fetching,
    Integrating,
    Validating,
    Pushing,
    Conflict,
    AwaitingUser,
    OfflineQueued,
    Backoff,
    SafeMode,
    Error,
}

#[derive(Debug, Error)]
pub enum SyncError {
    #[error(transparent)]
    Auth(#[from] auth::AuthError),
    #[error(transparent)]
    Git(#[from] git::GitError),
    #[error(transparent)]
    Recovery(#[from] recovery::RecoveryError),
    #[error(transparent)]
    Validate(#[from] crate::validate::ValidateError),
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("{0}")]
    Message(String),
    #[error("conflicts unresolved — resolve in UI before push")]
    UnresolvedConflicts,
    #[error("preflight blocked: secrets detected")]
    SecretsBlocked,
    #[error("validation blocked push")]
    ValidationBlocked,
    #[error("safe mode — restore required")]
    SafeMode,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncStatus {
    pub state: SyncState,
    pub auth: AuthStatus,
    pub remote_url: Option<String>,
    pub last_error: Option<String>,
    pub last_success_at: Option<DateTime<Utc>>,
    pub offline_queue: Vec<QueuedCommit>,
    pub history: Vec<HistoryEvent>,
    pub conflicts: Vec<ConflictItem>,
    pub preflight: Vec<PreflightWarning>,
    pub recovery_notes: Vec<String>,
    pub debounce_ms: u64,
    pub backoff_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncSettings {
    pub debounce_ms: u64,
    pub interval_ms: Option<u64>,
    pub sync_on_save: bool,
    pub sync_on_close: bool,
    pub sync_on_resume: bool,
}

impl Default for SyncSettings {
    fn default() -> Self {
        Self {
            debounce_ms: 1500,
            interval_ms: Some(300_000),
            sync_on_save: true,
            sync_on_close: true,
            sync_on_resume: true,
        }
    }
}

#[derive(Debug)]
pub struct SyncEngine {
    pub vault: PathBuf,
    pub state: SyncState,
    pub settings: SyncSettings,
    pub conflicts: Vec<ConflictItem>,
    pub preflight: Vec<PreflightWarning>,
    pub recovery_notes: Vec<String>,
    pub remote_url: Option<String>,
    pub last_error: Option<String>,
    pub last_success_at: Option<DateTime<Utc>>,
    pub backoff_ms: u64,
    debounce_deadline: Option<std::time::Instant>,
}

impl SyncEngine {
    pub fn open(vault: impl Into<PathBuf>) -> Result<Self, SyncError> {
        let vault = vault.into();
        std::fs::create_dir_all(vault.join(".brainflow/local/sync"))?;
        gitignore::ensure_brainflow_gitignore(&vault)?;

        let mut journal = recovery::load_journal(&vault)?;
        let notes = recovery::recover_from_interrupt(&mut journal);
        recovery::save_journal(&vault, &journal)?;

        Ok(Self {
            vault,
            state: journal.state,
            settings: SyncSettings::default(),
            conflicts: vec![],
            preflight: vec![],
            recovery_notes: notes,
            remote_url: journal.remote_url,
            last_error: journal.last_error,
            last_success_at: journal.last_success_at,
            backoff_ms: 2_000,
            debounce_deadline: None,
        })
    }

    pub fn status(&self) -> SyncStatus {
        SyncStatus {
            state: self.state.clone(),
            auth: auth::auth_status(),
            remote_url: self.remote_url.clone(),
            last_error: self.last_error.clone(),
            last_success_at: self.last_success_at,
            offline_queue: queue::load_queue(&self.vault).items,
            history: queue::load_history(&self.vault).events,
            conflicts: self.conflicts.clone(),
            preflight: self.preflight.clone(),
            recovery_notes: self.recovery_notes.clone(),
            debounce_ms: self.settings.debounce_ms,
            backoff_ms: self.backoff_ms,
        }
    }

    fn persist(&self, interrupted: InterruptedOp) -> Result<(), SyncError> {
        let journal = SyncJournal {
            schema_version: 1,
            state: self.state.clone(),
            interrupted_op: interrupted,
            last_error: self.last_error.clone(),
            last_success_at: self.last_success_at,
            updated_at: Utc::now(),
            op_token: uuid::Uuid::new_v4().to_string(),
            remote_url: self.remote_url.clone(),
            offline_queue_len: queue::load_queue(&self.vault).items.len(),
            notes: self.recovery_notes.clone(),
        };
        recovery::save_journal(&self.vault, &journal)?;
        Ok(())
    }

    /// Configure by cloning an existing private/public repo URL into the vault.
    pub fn configure_clone(&mut self, url: &str) -> Result<(), SyncError> {
        self.state = SyncState::Authenticating;
        self.persist(InterruptedOp::None)?;
        if !auth::auth_status().authenticated {
            return Err(SyncError::Message(
                "Authenticate first (PAT or device flow)".into(),
            ));
        }
        git::clone_repo(url, &self.vault)?;
        gitignore::ensure_brainflow_gitignore(&self.vault)?;
        self.remote_url = Some(url.to_string());
        self.state = SyncState::ReadyLocal;
        self.persist(InterruptedOp::None)?;
        self.state = SyncState::Idle;
        queue::push_history(&self.vault, "configure", &format!("cloned {url}"), true);
        self.persist(InterruptedOp::None)?;
        Ok(())
    }

    /// Init local repo + create private GitHub repo + set origin.
    pub fn configure_create_private(&mut self, name: &str) -> Result<RemoteRepo, SyncError> {
        self.state = SyncState::Authenticating;
        self.persist(InterruptedOp::None)?;
        git::init_repo(&self.vault)?;
        gitignore::ensure_brainflow_gitignore(&self.vault)?;
        let remote = auth::create_repository(&CreateRepoRequest {
            name: name.to_string(),
            private: true,
            description: Some("BrainFlow vault (private sync)".into()),
        })?;
        git::set_remote_origin(&self.vault, &remote.clone_url)?;
        self.remote_url = Some(remote.clone_url.clone());
        // Initial commit of layout.
        let _ = git::commit_all(&self.vault, "Initial BrainFlow vault")?;
        self.state = SyncState::ReadyLocal;
        self.persist(InterruptedOp::None)?;
        self.state = SyncState::Idle;
        queue::push_history(
            &self.vault,
            "configure",
            &format!("created private repo {}", remote.full_name),
            true,
        );
        self.persist(InterruptedOp::None)?;
        Ok(remote)
    }

    /// Notify filesystem change — starts debounce window.
    pub fn on_fs_change(&mut self) {
        if matches!(
            self.state,
            SyncState::Unconfigured | SyncState::Conflict | SyncState::AwaitingUser | SyncState::SafeMode
        ) {
            return;
        }
        self.state = SyncState::Debouncing;
        self.debounce_deadline = Some(
            std::time::Instant::now() + Duration::from_millis(self.settings.debounce_ms),
        );
        let _ = self.persist(InterruptedOp::None);
    }

    /// Advance debounce / backoff clocks; may start a sync cycle.
    pub fn tick(&mut self) -> Result<(), SyncError> {
        match self.state {
            SyncState::Debouncing => {
                if let Some(deadline) = self.debounce_deadline {
                    if std::time::Instant::now() >= deadline {
                        self.run_cycle(false)?;
                    }
                }
            }
            SyncState::Backoff | SyncState::OfflineQueued => {
                // Caller may invoke run_cycle when online.
            }
            _ => {}
        }
        Ok(())
    }

    /// Full cycle: snapshot → commit → fetch → integrate → validate → push.
    pub fn run_cycle(&mut self, offline: bool) -> Result<(), SyncError> {
        if matches!(self.state, SyncState::SafeMode) {
            return Err(SyncError::SafeMode);
        }
        if matches!(self.state, SyncState::Conflict | SyncState::AwaitingUser) {
            return Err(SyncError::UnresolvedConflicts);
        }

        // Soft integrity probe via gitoxide when a repo already exists.
        if self.vault.join(".git").exists() {
            if git::gix_integrity_ok(&self.vault).is_err() {
                self.state = SyncState::SafeMode;
                self.last_error = Some("gitoxide open failed — safe mode".into());
                self.persist(InterruptedOp::None)?;
                return Err(SyncError::SafeMode);
            }
        }

        // Preflight on dirty paths (best-effort listing via walk of common dirs).
        let candidates = list_portable_paths(&self.vault);
        self.preflight = preflight::scan_paths(&self.vault, &candidates);
        if preflight::secrets_block_commit(&self.preflight) {
            self.state = SyncState::Error;
            self.last_error = Some("Secret/credential pattern in staged content".into());
            queue::push_history(&self.vault, "preflight", "blocked secrets", false);
            self.persist(InterruptedOp::None)?;
            return Err(SyncError::SecretsBlocked);
        }

        self.state = SyncState::LockedSnapshot;
        self.persist(InterruptedOp::None)?;

        self.state = SyncState::Committing;
        self.persist(InterruptedOp::Commit)?;
        let summary = format!(
            "BrainFlow sync @ {}",
            Utc::now().format("%Y-%m-%d %H:%M:%S UTC")
        );
        match git::commit_all(&self.vault, &summary) {
            Ok(_) => {
                queue::push_history(&self.vault, "commit", &summary, true);
            }
            Err(e) => {
                if offline {
                    queue::enqueue(&self.vault, &summary, candidates);
                    self.state = SyncState::OfflineQueued;
                    self.persist(InterruptedOp::None)?;
                    return Ok(());
                }
                self.last_error = Some(e.to_string());
                self.state = SyncState::Error;
                self.persist(InterruptedOp::None)?;
                return Err(e.into());
            }
        }

        if offline || !auth::auth_status().authenticated {
            queue::enqueue(&self.vault, &summary, candidates);
            self.state = SyncState::OfflineQueued;
            self.persist(InterruptedOp::None)?;
            return Ok(());
        }

        self.state = SyncState::Fetching;
        self.persist(InterruptedOp::Fetch)?;
        if let Err(e) = git::fetch_origin(&self.vault) {
            self.last_error = Some(e.to_string());
            self.state = SyncState::Backoff;
            self.backoff_ms = (self.backoff_ms * 2).min(300_000);
            queue::push_history(&self.vault, "fetch", &e.to_string(), false);
            self.persist(InterruptedOp::None)?;
            return Err(e.into());
        }

        self.state = SyncState::Integrating;
        self.persist(InterruptedOp::Integrate)?;
        let IntegrateResult {
            clean,
            conflicts,
            merged_files,
        } = match git::integrate_origin(&self.vault) {
            Ok(r) => r,
            Err(e) => {
                // Integrity / unrelated histories → safe mode.
                if e.to_string().contains("no merge base") || e.to_string().contains("corrupt") {
                    self.state = SyncState::SafeMode;
                    self.last_error = Some(e.to_string());
                    self.persist(InterruptedOp::None)?;
                    return Err(SyncError::SafeMode);
                }
                self.last_error = Some(e.to_string());
                self.state = SyncState::Error;
                self.persist(InterruptedOp::None)?;
                return Err(e.into());
            }
        };
        if !merged_files.is_empty() {
            queue::push_history(
                &self.vault,
                "integrate",
                &format!("auto-merged {}", merged_files.join(", ")),
                true,
            );
        }
        if !clean {
            self.conflicts = conflicts;
            self.state = SyncState::Conflict;
            self.persist(InterruptedOp::None)?;
            queue::push_history(&self.vault, "conflict", "awaiting user resolution", false);
            return Err(SyncError::UnresolvedConflicts);
        }

        self.state = SyncState::Validating;
        self.persist(InterruptedOp::Validate)?;
        let report = crate::validate::validate_vault_workflows(&self.vault)?;
        if !report.ok {
            self.state = SyncState::Error;
            self.last_error = Some(report.errors.join("; "));
            queue::push_history(&self.vault, "validate", &report.errors.join("; "), false);
            self.persist(InterruptedOp::None)?;
            return Err(SyncError::ValidationBlocked);
        }

        self.state = SyncState::Pushing;
        self.persist(InterruptedOp::Push)?;
        // Never force.
        match git::push_origin(&self.vault, false) {
            Ok(()) => {
                self.state = SyncState::Idle;
                self.last_success_at = Some(Utc::now());
                self.last_error = None;
                self.backoff_ms = 2_000;
                let drained = queue::drain_queue(&self.vault);
                queue::push_history(
                    &self.vault,
                    "push",
                    &format!("ok; drained {} offline queue item(s)", drained.len()),
                    true,
                );
                self.persist(InterruptedOp::None)?;
                Ok(())
            }
            Err(e) => {
                let msg = e.to_string();
                // Non-fast-forward → back to fetch/integrate on next cycle; never force.
                self.last_error = Some(msg.clone());
                self.state = SyncState::Backoff;
                self.backoff_ms = (self.backoff_ms * 2).min(300_000);
                queue::push_history(&self.vault, "push", &msg, false);
                self.persist(InterruptedOp::None)?;
                Err(e.into())
            }
        }
    }

    /// Apply user conflict resolutions (write chosen content) and resume integrate path.
    pub fn resolve_conflicts(&mut self, resolutions: Vec<ConflictResolution>) -> Result<(), SyncError> {
        for r in resolutions {
            let path = self.vault.join(&r.path);
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::write(path, r.content)?;
        }
        self.conflicts.clear();
        self.state = SyncState::Integrating;
        // Commit resolutions then validate+push.
        let _ = git::commit_all(&self.vault, "Resolve sync conflicts")?;
        self.state = SyncState::Validating;
        let report = crate::validate::validate_vault_workflows(&self.vault)?;
        if !report.ok {
            self.state = SyncState::Conflict;
            self.last_error = Some(report.errors.join("; "));
            return Err(SyncError::ValidationBlocked);
        }
        self.state = SyncState::Pushing;
        git::push_origin(&self.vault, false)?;
        self.state = SyncState::Idle;
        self.last_success_at = Some(Utc::now());
        queue::push_history(&self.vault, "resolve", "conflicts resolved and pushed", true);
        self.persist(InterruptedOp::None)?;
        Ok(())
    }

    pub fn force_push_forbidden() -> bool {
        git::force_push_forbidden()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConflictResolution {
    pub path: String,
    /// Chosen content (local, remote, or manually edited merge).
    pub content: String,
}

fn list_portable_paths(vault: &Path) -> Vec<String> {
    let mut out = Vec::new();
    let mut stack = vec![vault.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let Ok(rd) = std::fs::read_dir(&dir) else {
            continue;
        };
        for entry in rd.flatten() {
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().to_string();
            if name == ".git" {
                continue;
            }
            if name == "local" && dir.ends_with(".brainflow") {
                continue;
            }
            if path.is_dir() {
                stack.push(path);
            } else if let Ok(rel) = path.strip_prefix(vault) {
                out.push(rel.to_string_lossy().replace('\\', "/"));
            }
        }
    }
    out
}
