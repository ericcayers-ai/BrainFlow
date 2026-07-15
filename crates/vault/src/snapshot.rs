//! Local recovery snapshots for crash / accidental overwrite awareness.

use crate::{atomic_write_json, atomic_write_text, content_hash, resolve_in_vault, VaultError};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnapshotMeta {
    pub id: String,
    pub note_path: String,
    pub created_at: DateTime<Utc>,
    pub content_hash: String,
    pub reason: String,
}

fn recovery_root(vault: &Path) -> PathBuf {
    vault.join(".brainflow/local/recovery")
}

fn sanitize_note_key(note_path: &str) -> String {
    note_path.replace(['/', '\\', ':'], "__")
}

/// Write a snapshot of the note body under `.brainflow/local/recovery/` (gitignored).
pub fn write_snapshot(
    root: &Path,
    note_path: &str,
    content: &str,
    reason: &str,
) -> Result<SnapshotMeta, VaultError> {
    let id = Uuid::new_v4().to_string();
    let meta = SnapshotMeta {
        id: id.clone(),
        note_path: note_path.to_string(),
        created_at: Utc::now(),
        content_hash: content_hash(content.as_bytes()),
        reason: reason.to_string(),
    };
    let dir = recovery_root(root).join(sanitize_note_key(note_path));
    fs::create_dir_all(&dir)?;
    let body_path = dir.join(format!("{id}.md"));
    let meta_path = dir.join(format!("{id}.json"));
    atomic_write_text(&body_path, content)?;
    atomic_write_json(&meta_path, &meta)?;
    // Cap history per note (keep newest 20).
    prune_snapshots(&dir, 20)?;
    Ok(meta)
}

fn prune_snapshots(dir: &Path, keep: usize) -> Result<(), VaultError> {
    let mut metas: Vec<(PathBuf, SnapshotMeta)> = Vec::new();
    if !dir.exists() {
        return Ok(());
    }
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        if let Ok(text) = fs::read_to_string(&path) {
            if let Ok(meta) = serde_json::from_str::<SnapshotMeta>(&text) {
                metas.push((path, meta));
            }
        }
    }
    metas.sort_by(|a, b| b.1.created_at.cmp(&a.1.created_at));
    for (meta_path, meta) in metas.into_iter().skip(keep) {
        let _ = fs::remove_file(&meta_path);
        let body = meta_path.with_extension("md");
        let alt = meta_path
            .parent()
            .unwrap_or(dir)
            .join(format!("{}.md", meta.id));
        let _ = fs::remove_file(body);
        let _ = fs::remove_file(alt);
    }
    Ok(())
}

pub fn list_snapshots(root: &Path, note_path: &str) -> Result<Vec<SnapshotMeta>, VaultError> {
    let dir = recovery_root(root).join(sanitize_note_key(note_path));
    let mut out = Vec::new();
    if !dir.exists() {
        return Ok(out);
    }
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let text = fs::read_to_string(path)?;
        if let Ok(meta) = serde_json::from_str::<SnapshotMeta>(&text) {
            out.push(meta);
        }
    }
    out.sort_by(|a, b| b.created_at.cmp(&a.created_at));
    Ok(out)
}

pub fn read_snapshot(root: &Path, note_path: &str, snapshot_id: &str) -> Result<String, VaultError> {
    let path = recovery_root(root)
        .join(sanitize_note_key(note_path))
        .join(format!("{snapshot_id}.md"));
    Ok(fs::read_to_string(path)?)
}

pub fn restore_snapshot(
    root: &Path,
    note_path: &str,
    snapshot_id: &str,
) -> Result<String, VaultError> {
    let content = read_snapshot(root, note_path, snapshot_id)?;
    // Snapshot current before restore.
    if let Ok(current) = crate::read_text(root, note_path) {
        let _ = write_snapshot(root, note_path, &current, "pre-restore");
    }
    let dest = resolve_in_vault(root, note_path)?;
    atomic_write_text(&dest, &content)?;
    Ok(content)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{open_vault, save_note};
    use tempfile::tempdir;

    #[test]
    fn snapshot_and_restore() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        save_note(&info.root, "notes/x.md", "v1\n").unwrap();
        let snap = write_snapshot(&info.root, "notes/x.md", "v1\n", "autosave").unwrap();
        save_note(&info.root, "notes/x.md", "v2\n").unwrap();
        let restored = restore_snapshot(&info.root, "notes/x.md", &snap.id).unwrap();
        assert_eq!(restored, "v1\n");
        assert_eq!(crate::read_text(&info.root, "notes/x.md").unwrap(), "v1\n");
    }
}
