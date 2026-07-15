//! Bookmarks and named workspace layouts under `.brainflow/`.

use crate::{atomic_write_json, ensure_layout, resolve_in_vault, VaultError};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

const BOOKMARKS_REL: &str = ".brainflow/bookmarks.json";
const WORKSPACES_DIR: &str = ".brainflow/workspaces";

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BookmarkEntry {
    pub path: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub pinned: bool,
    #[serde(default)]
    pub created_ms: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct BookmarkStore {
    pub schema_version: u32,
    pub items: Vec<BookmarkEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkspaceTab {
    pub path: String,
    #[serde(default)]
    pub pinned: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceLayout {
    pub schema_version: u32,
    pub id: String,
    pub title: String,
    pub tabs: Vec<WorkspaceTab>,
    pub active_path: String,
    #[serde(default)]
    pub split_path: Option<String>,
    #[serde(default = "default_editor_mode")]
    pub editor_mode: String,
    #[serde(default = "default_surface")]
    pub vault_surface: String,
    #[serde(default)]
    pub rail_collapsed: bool,
}

fn default_editor_mode() -> String {
    "source".into()
}

fn default_surface() -> String {
    "note".into()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceListItem {
    pub id: String,
    pub title: String,
    pub path: String,
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

pub fn load_bookmarks(root: &Path) -> Result<BookmarkStore, VaultError> {
    ensure_layout(root)?;
    let path = resolve_in_vault(root, BOOKMARKS_REL)?;
    if !path.exists() {
        return Ok(BookmarkStore {
            schema_version: 1,
            items: vec![],
        });
    }
    let text = fs::read_to_string(path)?;
    let mut store: BookmarkStore = serde_json::from_str(&text)?;
    if store.schema_version == 0 {
        store.schema_version = 1;
    }
    Ok(store)
}

pub fn save_bookmarks(root: &Path, store: &BookmarkStore) -> Result<(), VaultError> {
    ensure_layout(root)?;
    let path = resolve_in_vault(root, BOOKMARKS_REL)?;
    atomic_write_json(&path, store)
}

pub fn toggle_bookmark(
    root: &Path,
    path: &str,
    title: &str,
) -> Result<BookmarkStore, VaultError> {
    let mut store = load_bookmarks(root)?;
    let norm = path.replace('\\', "/");
    if let Some(idx) = store.items.iter().position(|b| b.path == norm) {
        store.items.remove(idx);
    } else {
        store.items.push(BookmarkEntry {
            path: norm,
            title: if title.is_empty() {
                path_title(path)
            } else {
                title.to_string()
            },
            pinned: false,
            created_ms: Some(now_ms()),
        });
    }
    save_bookmarks(root, &store)?;
    Ok(store)
}

fn path_title(path: &str) -> String {
    Path::new(path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(path)
        .to_string()
}

pub fn list_workspaces(root: &Path) -> Result<Vec<WorkspaceListItem>, VaultError> {
    ensure_layout(root)?;
    let dir = root.join(WORKSPACES_DIR);
    fs::create_dir_all(&dir)?;
    let mut out = Vec::new();
    for entry in fs::read_dir(&dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let text = match fs::read_to_string(&path) {
            Ok(t) => t,
            Err(_) => continue,
        };
        let layout: WorkspaceLayout = match serde_json::from_str(&text) {
            Ok(l) => l,
            Err(_) => continue,
        };
        let rel = format!(
            "{}/{}",
            WORKSPACES_DIR,
            path.file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("workspace.json")
        );
        out.push(WorkspaceListItem {
            id: layout.id,
            title: layout.title,
            path: rel,
        });
    }
    out.sort_by(|a, b| a.title.to_ascii_lowercase().cmp(&b.title.to_ascii_lowercase()));
    Ok(out)
}

pub fn save_workspace(root: &Path, layout: &WorkspaceLayout) -> Result<String, VaultError> {
    ensure_layout(root)?;
    let dir = root.join(WORKSPACES_DIR);
    fs::create_dir_all(&dir)?;
    let id = if layout.id.trim().is_empty() {
        slugify_id(&layout.title)
    } else {
        slugify_id(&layout.id)
    };
    let mut to_save = layout.clone();
    to_save.schema_version = 1;
    to_save.id = id.clone();
    let rel = format!("{WORKSPACES_DIR}/{id}.json");
    let path = resolve_in_vault(root, &rel)?;
    atomic_write_json(&path, &to_save)?;
    Ok(rel)
}

pub fn load_workspace(root: &Path, id_or_path: &str) -> Result<WorkspaceLayout, VaultError> {
    let rel = if id_or_path.contains('/') || id_or_path.ends_with(".json") {
        id_or_path.replace('\\', "/")
    } else {
        format!("{WORKSPACES_DIR}/{}.json", slugify_id(id_or_path))
    };
    let path = resolve_in_vault(root, &rel)?;
    let text = fs::read_to_string(path)?;
    let mut layout: WorkspaceLayout = serde_json::from_str(&text)?;
    if layout.schema_version == 0 {
        layout.schema_version = 1;
    }
    Ok(layout)
}

pub fn delete_workspace(root: &Path, id: &str) -> Result<(), VaultError> {
    let rel = format!("{WORKSPACES_DIR}/{}.json", slugify_id(id));
    let path = resolve_in_vault(root, &rel)?;
    if path.exists() {
        fs::remove_file(path)?;
    }
    Ok(())
}

fn slugify_id(s: &str) -> String {
    let mut out = String::new();
    for ch in s.trim().chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch.to_ascii_lowercase());
        } else if ch == '-' || ch == '_' || ch.is_whitespace() {
            if !out.ends_with('-') {
                out.push('-');
            }
        }
    }
    let trimmed = out.trim_matches('-').to_string();
    if trimmed.is_empty() {
        format!("workspace-{}", now_ms())
    } else {
        trimmed
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::open_vault;
    use tempfile::tempdir;

    #[test]
    fn bookmarks_toggle_and_workspaces_roundtrip() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();

        let store = toggle_bookmark(&info.root, "notes/a.md", "A").unwrap();
        assert_eq!(store.items.len(), 1);
        let store = toggle_bookmark(&info.root, "notes/a.md", "A").unwrap();
        assert!(store.items.is_empty());

        let layout = WorkspaceLayout {
            schema_version: 1,
            id: "focus".into(),
            title: "Focus".into(),
            tabs: vec![WorkspaceTab {
                path: "notes/a.md".into(),
                pinned: true,
            }],
            active_path: "notes/a.md".into(),
            split_path: None,
            editor_mode: "live".into(),
            vault_surface: "note".into(),
            rail_collapsed: false,
        };
        let rel = save_workspace(&info.root, &layout).unwrap();
        assert!(rel.ends_with("focus.json"));
        let loaded = load_workspace(&info.root, "focus").unwrap();
        assert_eq!(loaded.active_path, "notes/a.md");
        assert_eq!(list_workspaces(&info.root).unwrap().len(), 1);
    }
}
