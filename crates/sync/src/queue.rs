//! Offline commit queue and sync history panel data.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueuedCommit {
    pub id: String,
    pub summary: String,
    pub created_at: DateTime<Utc>,
    pub paths: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryEvent {
    pub id: String,
    pub at: DateTime<Utc>,
    pub kind: String,
    pub detail: String,
    pub ok: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct OfflineQueue {
    pub items: Vec<QueuedCommit>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SyncHistory {
    pub events: Vec<HistoryEvent>,
}

fn queue_path(vault: &Path) -> std::path::PathBuf {
    vault.join(".brainflow/local/sync/offline_queue.json")
}

fn history_path(vault: &Path) -> std::path::PathBuf {
    vault.join(".brainflow/local/sync/history.json")
}

pub fn load_queue(vault: &Path) -> OfflineQueue {
    let path = queue_path(vault);
    std::fs::read_to_string(path)
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_default()
}

pub fn save_queue(vault: &Path, q: &OfflineQueue) -> std::io::Result<()> {
    let path = queue_path(vault);
    if let Some(p) = path.parent() {
        std::fs::create_dir_all(p)?;
    }
    std::fs::write(path, serde_json::to_string_pretty(q).unwrap_or_default())
}

pub fn enqueue(vault: &Path, summary: &str, paths: Vec<String>) -> QueuedCommit {
    let mut q = load_queue(vault);
    // Idempotent enqueue: same summary+paths while already queued → return existing (AC-SYNC-05).
    if let Some(existing) = q.items.iter().find(|i| i.summary == summary && i.paths == paths) {
        return existing.clone();
    }
    let item = QueuedCommit {
        id: Uuid::new_v4().to_string(),
        summary: summary.to_string(),
        created_at: Utc::now(),
        paths,
    };
    q.items.push(item.clone());
    let _ = save_queue(vault, &q);
    item
}

/// Drain all queued items (after successful reconnect push). Returns drained commits.
pub fn drain_queue(vault: &Path) -> Vec<QueuedCommit> {
    let q = load_queue(vault);
    let items = q.items;
    let _ = save_queue(vault, &OfflineQueue::default());
    items
}

/// Clear without returning drained items (UI / tests).
#[allow(dead_code)]
pub fn clear_queue(vault: &Path) {
    let _ = drain_queue(vault);
}

pub fn load_history(vault: &Path) -> SyncHistory {
    let path = history_path(vault);
    std::fs::read_to_string(path)
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_default()
}

pub fn push_history(vault: &Path, kind: &str, detail: &str, ok: bool) {
    let mut h = load_history(vault);
    h.events.push(HistoryEvent {
        id: Uuid::new_v4().to_string(),
        at: Utc::now(),
        kind: kind.into(),
        detail: detail.into(),
        ok,
    });
    // Cap history.
    if h.events.len() > 200 {
        let skip = h.events.len() - 200;
        h.events = h.events.split_off(skip);
    }
    let path = history_path(vault);
    if let Some(p) = path.parent() {
        let _ = std::fs::create_dir_all(p);
    }
    let _ = std::fs::write(path, serde_json::to_string_pretty(&h).unwrap_or_default());
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn enqueue_idempotent_same_summary_paths() {
        let dir = tempdir().unwrap();
        let a = enqueue(dir.path(), "offline edit", vec!["a.md".into()]);
        let b = enqueue(dir.path(), "offline edit", vec!["a.md".into()]);
        assert_eq!(a.id, b.id);
        assert_eq!(load_queue(dir.path()).items.len(), 1);
    }

    #[test]
    fn drain_clears_without_duplicates() {
        let dir = tempdir().unwrap();
        enqueue(dir.path(), "one", vec!["1.md".into()]);
        enqueue(dir.path(), "two", vec!["2.md".into()]);
        let drained = drain_queue(dir.path());
        assert_eq!(drained.len(), 2);
        assert!(load_queue(dir.path()).items.is_empty());
        // Second drain is empty (idempotent drain for already-flushed queue).
        assert!(drain_queue(dir.path()).is_empty());
    }
}
