//! Vault file explorer listing (Markdown-centric).

use crate::{resolve_in_vault, VaultError};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EntryKind {
    Dir,
    Note,
    File,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VaultEntry {
    pub relative_path: String,
    pub name: String,
    pub kind: EntryKind,
    pub children: Option<Vec<VaultEntry>>,
}

fn to_rel(root: &Path, path: &Path) -> Result<String, VaultError> {
    let rel = path
        .strip_prefix(root)
        .map_err(|_| VaultError::PathEscape)?;
    Ok(rel.to_string_lossy().replace('\\', "/"))
}

fn is_markdown(path: &Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|e| e.eq_ignore_ascii_case("md"))
        .unwrap_or(false)
}

/// List a single directory (non-recursive children). Skips hidden `.git` by default;
/// `.brainflow` is included so Bases/templates remain discoverable.
pub fn list_dir(root: &Path, relative: &str) -> Result<Vec<VaultEntry>, VaultError> {
    let dir = if relative.is_empty() || relative == "." {
        root.to_path_buf()
    } else {
        resolve_in_vault(root, relative)?
    };
    if !dir.is_dir() {
        return Err(VaultError::InvalidPath(format!(
            "not a directory: {}",
            dir.display()
        )));
    }
    let mut entries = Vec::new();
    let mut read = fs::read_dir(&dir)?;
    while let Some(item) = read.next() {
        let item = item?;
        let name = item.file_name().to_string_lossy().to_string();
        if name == ".git" || name == "node_modules" {
            continue;
        }
        let path = item.path();
        let relative_path = to_rel(root, &path)?;
        let meta = item.metadata()?;
        if meta.is_dir() {
            entries.push(VaultEntry {
                relative_path,
                name,
                kind: EntryKind::Dir,
                children: None,
            });
        } else if is_markdown(&path) {
            entries.push(VaultEntry {
                relative_path,
                name,
                kind: EntryKind::Note,
                children: None,
            });
        } else {
            entries.push(VaultEntry {
                relative_path,
                name,
                kind: EntryKind::File,
                children: None,
            });
        }
    }
    entries.sort_by(|a, b| {
        use std::cmp::Ordering;
        match (&a.kind, &b.kind) {
            (EntryKind::Dir, EntryKind::Dir) => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
            (EntryKind::Dir, _) => Ordering::Less,
            (_, EntryKind::Dir) => Ordering::Greater,
            _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
        }
    });
    Ok(entries)
}

/// Recursively collect Markdown note paths under the vault (skips `.git`).
pub fn list_note_paths(root: &Path) -> Result<Vec<String>, VaultError> {
    let mut out = Vec::new();
    walk_notes(root, root, &mut out)?;
    out.sort();
    Ok(out)
}

fn walk_notes(root: &Path, dir: &Path, out: &mut Vec<String>) -> Result<(), VaultError> {
    for item in fs::read_dir(dir)? {
        let item = item?;
        let name = item.file_name().to_string_lossy().to_string();
        if name == ".git" || name == "node_modules" {
            continue;
        }
        let path = item.path();
        if path.is_dir() {
            // Skip recovery dumps and local indexes if nested oddly.
            if name == "local" && dir.ends_with(".brainflow") {
                continue;
            }
            walk_notes(root, &path, out)?;
        } else if is_markdown(&path) {
            out.push(to_rel(root, &path)?);
        }
    }
    Ok(())
}

/// Flat list shaped for quick switcher (path + display name).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NoteListItem {
    pub path: String,
    pub name: String,
}

pub fn list_notes_for_switcher(root: &Path) -> Result<Vec<NoteListItem>, VaultError> {
    Ok(list_note_paths(root)?
        .into_iter()
        .map(|path| {
            let name = Path::new(&path)
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or(&path)
                .to_string();
            NoteListItem { path, name }
        })
        .collect())
}

/// Create an empty note path with optional seed content.
pub fn create_note(root: &Path, relative: &str, content: &str) -> Result<PathBuf, VaultError> {
    let path = resolve_in_vault(root, relative)?;
    if path.exists() {
        return Err(VaultError::InvalidPath(format!(
            "already exists: {relative}"
        )));
    }
    crate::atomic_write_text(&path, content)?;
    Ok(path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{open_vault, save_note};
    use tempfile::tempdir;

    #[test]
    fn lists_notes_tree() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        save_note(&info.root, "notes/a.md", "# A\n").unwrap();
        save_note(&info.root, "notes/sub/b.md", "# B\n").unwrap();
        let paths = list_note_paths(&info.root).unwrap();
        assert!(paths.iter().any(|p| p == "notes/a.md"));
        assert!(paths.iter().any(|p| p.ends_with("notes/sub/b.md") || p == "notes/sub/b.md"));
        let entries = list_dir(&info.root, "notes").unwrap();
        assert!(entries.iter().any(|e| e.name == "a.md"));
    }
}
