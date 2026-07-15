//! Durable sync status journal and interrupted-operation recovery.

use crate::state::SyncState;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Error)]
pub enum RecoveryError {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum InterruptedOp {
    None,
    Commit,
    Fetch,
    Integrate,
    Validate,
    Push,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncJournal {
    pub schema_version: u32,
    pub state: SyncState,
    pub interrupted_op: InterruptedOp,
    pub last_error: Option<String>,
    pub last_success_at: Option<DateTime<Utc>>,
    pub updated_at: DateTime<Utc>,
    pub op_token: String,
    pub remote_url: Option<String>,
    pub offline_queue_len: usize,
    pub notes: Vec<String>,
}

impl Default for SyncJournal {
    fn default() -> Self {
        Self {
            schema_version: 1,
            state: SyncState::Unconfigured,
            interrupted_op: InterruptedOp::None,
            last_error: None,
            last_success_at: None,
            updated_at: Utc::now(),
            op_token: Uuid::new_v4().to_string(),
            remote_url: None,
            offline_queue_len: 0,
            notes: vec![],
        }
    }
}

pub fn journal_path(vault: &Path) -> PathBuf {
    vault.join(".brainflow/local/sync/journal.json")
}

pub fn load_journal(vault: &Path) -> Result<SyncJournal, RecoveryError> {
    let path = journal_path(vault);
    if !path.exists() {
        return Ok(SyncJournal::default());
    }
    let text = std::fs::read_to_string(path)?;
    Ok(serde_json::from_str(&text)?)
}

pub fn save_journal(vault: &Path, journal: &SyncJournal) -> Result<(), RecoveryError> {
    let path = journal_path(vault);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("json.tmp");
    std::fs::write(&tmp, serde_json::to_string_pretty(journal)?)?;
    std::fs::rename(tmp, path)?;
    Ok(())
}

/// After crash/remount: map interrupted op to a recoverable state + operator notes.
pub fn recover_from_interrupt(journal: &mut SyncJournal) -> Vec<String> {
    let mut notes = Vec::new();
    match journal.interrupted_op {
        InterruptedOp::None => {}
        InterruptedOp::Commit => {
            notes.push(
                "Interrupted during commit. Local index may have staged files; re-run sync to retry commit (no remote change)."
                    .into(),
            );
            journal.state = SyncState::Idle;
            journal.interrupted_op = InterruptedOp::None;
        }
        InterruptedOp::Fetch => {
            notes.push(
                "Interrupted during fetch. Safe to retry fetch; no local history rewritten.".into(),
            );
            journal.state = SyncState::Backoff;
            journal.interrupted_op = InterruptedOp::None;
        }
        InterruptedOp::Integrate => {
            notes.push(
                "Interrupted during integrate. Check .brainflow/local/sync/recovery/ for side copies; resolve conflicts in UI before push."
                    .into(),
            );
            journal.state = SyncState::Conflict;
            journal.interrupted_op = InterruptedOp::None;
        }
        InterruptedOp::Validate => {
            notes.push(
                "Interrupted during validation. Re-run validate; push remains blocked until schemas pass."
                    .into(),
            );
            journal.state = SyncState::Validating;
            journal.interrupted_op = InterruptedOp::None;
        }
        InterruptedOp::Push => {
            notes.push(
                "Interrupted mid-push (AC-SYNC-01). Remote may or may not have received the update; next sync will fetch first. Never force-push to 'fix'."
                    .into(),
            );
            journal.state = SyncState::Backoff;
            journal.interrupted_op = InterruptedOp::None;
        }
    }
    journal.notes.extend(notes.clone());
    journal.updated_at = Utc::now();
    notes
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn recovers_mid_push() {
        let mut j = SyncJournal {
            interrupted_op: InterruptedOp::Push,
            state: SyncState::Pushing,
            ..Default::default()
        };
        let notes = recover_from_interrupt(&mut j);
        assert!(!notes.is_empty());
        assert_eq!(j.state, SyncState::Backoff);
        assert_eq!(j.interrupted_op, InterruptedOp::None);
    }

    #[test]
    fn journal_roundtrip() {
        let dir = tempdir().unwrap();
        let mut j = SyncJournal::default();
        j.state = SyncState::Idle;
        save_journal(dir.path(), &j).unwrap();
        let loaded = load_journal(dir.path()).unwrap();
        assert_eq!(loaded.state, SyncState::Idle);
    }
}
