//! Vault filesystem helpers: ensure portable layout, atomic note writes,

//! Markdown analysis, explorer, snapshots, templates, and portable foundations.



mod bases;

mod canvas;

mod explorer;

mod foundations;

mod links;

mod markdown;

mod properties;

mod rename;

mod snapshot;

mod templates;

mod workspace_meta;



use chrono::{DateTime, Utc};

use serde::{Deserialize, Serialize};

use sha2::{Digest, Sha256};

use std::fs;

use std::io::Write;

use std::path::{Path, PathBuf};

use thiserror::Error;

use uuid::Uuid;



pub use explorer::{

    create_note, list_dir, list_note_paths, list_notes_for_switcher, EntryKind, NoteListItem,

    VaultEntry,

};

pub use bases::{
    base_rows, eval_formula, load_base, save_base, BaseDefinition, BaseFilter, BaseRow, BaseSort,
};

pub use properties::{
    property_schema_suggestions, set_note_property, upsert_frontmatter_field, PropertySuggestion,
};

pub use workspace_meta::{
    delete_workspace, list_workspaces, load_bookmarks, load_workspace, save_bookmarks,
    save_workspace, toggle_bookmark, BookmarkEntry, BookmarkStore, WorkspaceLayout,
    WorkspaceListItem, WorkspaceTab,
};

pub use canvas::{
    import_file_bytes, import_text_file, list_canvases, read_canvas, write_canvas, CanvasDoc,
    CanvasEdge, CanvasListItem, CanvasNode,
};

pub use foundations::{ensure_bases_canvas_foundations, FoundationPaths};

pub use links::{collect_all_links, links_for_note, list_tags, LinkRef, NoteLinks, TagEntry};

pub use markdown::{

    analyze_note, extract_inline_tags, extract_wikilinks, parse_frontmatter_yaml,

    resolve_wikilink_target, split_frontmatter, wikilink_matching_target, Frontmatter,
    NoteAnalysis, Wikilink,

};

pub use rename::{rename_note, RenameResult};

pub use snapshot::{

    list_snapshots, read_snapshot, restore_snapshot, write_snapshot, SnapshotMeta,

};

pub use templates::{
    apply_template, create_unique_note, ensure_default_templates, list_templates,
    open_or_create_daily_note, random_note_path, render_template, TemplateInfo,
};



#[derive(Debug, Error)]

pub enum VaultError {

    #[error("io error: {0}")]

    Io(#[from] std::io::Error),

    #[error("json error: {0}")]

    Json(#[from] serde_json::Error),

    #[error("invalid vault path: {0}")]

    InvalidPath(String),

    #[error("path escapes vault root")]

    PathEscape,

}



#[derive(Debug, Clone, Serialize, Deserialize)]

pub struct VaultInfo {

    pub root: PathBuf,

    pub opened_at: DateTime<Utc>,

    pub onedrive_warning: bool,

}



#[derive(Debug, Clone, Serialize, Deserialize)]

pub struct VaultJson {

    pub schema_version: u32,

    pub display_name: String,

}



impl Default for VaultJson {

    fn default() -> Self {

        Self {

            schema_version: 1,

            display_name: "BrainFlow Vault".into(),

        }

    }

}



#[derive(Debug, Clone, Serialize, Deserialize)]

pub struct NoteStat {

    pub relative_path: String,

    pub exists: bool,

    pub content_hash: Option<String>,

    pub modified_ms: Option<u64>,

    pub size: Option<u64>,

}



pub fn looks_like_cloud_sync_root(path: &Path) -> bool {

    let s = path.to_string_lossy().to_lowercase();

    s.contains("onedrive")

        || s.contains("dropbox")

        || s.contains("google drive")

        || s.contains("icloud")

}



pub fn open_vault(root: impl AsRef<Path>) -> Result<VaultInfo, VaultError> {

    let root = root.as_ref().canonicalize().map_err(|e| {

        VaultError::InvalidPath(format!("{} ({e})", root.as_ref().display()))

    })?;

    if !root.is_dir() {

        return Err(VaultError::InvalidPath(format!(

            "not a directory: {}",

            root.display()

        )));

    }

    ensure_layout(&root)?;

    let _ = ensure_default_templates(&root);

    let _ = ensure_bases_canvas_foundations(&root);

    Ok(VaultInfo {

        root: root.clone(),

        opened_at: Utc::now(),

        onedrive_warning: looks_like_cloud_sync_root(&root),

    })

}



/// Create a new vault directory (must not already contain a conflicting file at path).

pub fn create_vault(root: impl AsRef<Path>, display_name: &str) -> Result<VaultInfo, VaultError> {

    let root = root.as_ref();

    fs::create_dir_all(root)?;

    ensure_layout(root)?;

    let vault_json = root.join(".brainflow/vault.json");

    let v = VaultJson {

        schema_version: 1,

        display_name: display_name.to_string(),

    };

    atomic_write_json(&vault_json, &v)?;

    ensure_default_templates(root)?;

    ensure_bases_canvas_foundations(root)?;

    open_vault(root)

}



pub fn ensure_layout(root: &Path) -> Result<(), VaultError> {

    let dirs = [

        root.join(".brainflow"),

        root.join(".brainflow/workflows"),

        root.join(".brainflow/artifacts"),

        root.join(".brainflow/graphs"),

        root.join(".brainflow/graphs/canvas"),

        root.join(".brainflow/bases"),

        root.join(".brainflow/templates"),

        root.join(".brainflow/runs"),

        root.join(".brainflow/local"),

        root.join(".brainflow/local/recovery"),

        root.join("notes"),

        root.join("notes/daily"),

    ];

    for d in dirs {

        fs::create_dir_all(&d)?;

    }

    let vault_json = root.join(".brainflow/vault.json");

    if !vault_json.exists() {

        let v = VaultJson::default();

        atomic_write_json(&vault_json, &v)?;

    }

    let gitignore = root.join(".gitignore");

    if !gitignore.exists() {

        atomic_write_text(

            &gitignore,

            concat!(
                "# BrainFlow — do not sync machine-local or secret data\n",
                "*.sqlite\n*.sqlite-*\n*.db\n*.db-journal\n",
                ".brainflow/local/\n.brainflow/cache/\n.brainflow/embeddings/\n**/embeddings/\n",
                ".env\n.env.*\n!.env.example\n*.pem\n*.key\nsecrets/\n.credentials/\n",
                ".brainflow/tmp/\n.brainflow/extract/\n**/__pycache__/\n*.tmp\n*.temp\n*.partial\n",
                ".brainflow/device.json\n.brainflow/machine.json\n.brainflow/logs/\n*.log\n",
                ".DS_Store\nThumbs.db\ndesktop.ini\n*.swp\n*~\n",
            ),

        )?;

    }

    Ok(())

}



/// Resolve a vault-relative path; rejects `..` escape.

pub fn resolve_in_vault(root: &Path, relative: &str) -> Result<PathBuf, VaultError> {

    let rel = Path::new(relative.trim_start_matches(['/', '\\']));

    if rel

        .components()

        .any(|c| matches!(c, std::path::Component::ParentDir))

    {

        return Err(VaultError::PathEscape);

    }

    let joined = root.join(rel);

    let canon_root = root.canonicalize()?;

    // Parent may not exist yet — canonicalize parent when possible.

    if let Some(parent) = joined.parent() {

        if parent.exists() {

            let canon_parent = parent.canonicalize()?;

            if !canon_parent.starts_with(&canon_root) {

                return Err(VaultError::PathEscape);

            }

        }

    }

    Ok(joined)

}



pub fn read_text(root: &Path, relative: &str) -> Result<String, VaultError> {

    let path = resolve_in_vault(root, relative)?;

    Ok(fs::read_to_string(path)?)

}



pub fn note_stat(root: &Path, relative: &str) -> Result<NoteStat, VaultError> {

    let path = resolve_in_vault(root, relative)?;

    if !path.exists() {

        return Ok(NoteStat {

            relative_path: relative.to_string(),

            exists: false,

            content_hash: None,

            modified_ms: None,

            size: None,

        });

    }

    let meta = fs::metadata(&path)?;

    let modified_ms = meta

        .modified()

        .ok()

        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())

        .map(|d| d.as_millis() as u64);

    let bytes = fs::read(&path)?;

    Ok(NoteStat {

        relative_path: relative.to_string(),

        exists: true,

        content_hash: Some(content_hash(&bytes)),

        modified_ms,

        size: Some(bytes.len() as u64),

    })

}



pub fn atomic_write_text(path: &Path, content: &str) -> Result<(), VaultError> {

    if let Some(parent) = path.parent() {

        fs::create_dir_all(parent)?;

    }

    let tmp = path.with_extension(format!(

        "tmp-{}-{}",

        std::process::id(),

        Uuid::new_v4()

    ));

    {

        let mut f = fs::File::create(&tmp)?;

        f.write_all(content.as_bytes())?;

        f.sync_all()?;

    }

    fs::rename(&tmp, path)?;

    Ok(())

}



pub fn atomic_write_json<T: Serialize>(path: &Path, value: &T) -> Result<(), VaultError> {

    let content = serde_json::to_string_pretty(value)?;

    atomic_write_text(path, &format!("{content}\n"))

}



pub fn save_note(root: &Path, relative: &str, content: &str) -> Result<(), VaultError> {

    let path = resolve_in_vault(root, relative)?;

    // Snapshot previous version when overwriting non-empty existing content.

    if path.exists() {

        if let Ok(prev) = fs::read_to_string(&path) {

            if prev != content && !prev.is_empty() {

                let _ = write_snapshot(root, relative, &prev, "pre-save");

            }

        }

    }

    atomic_write_text(&path, content)

}



pub fn content_hash(bytes: &[u8]) -> String {

    let mut hasher = Sha256::new();

    hasher.update(bytes);

    format!("sha256:{}", hex::encode(hasher.finalize()))

}



#[cfg(test)]

mod tests {

    use super::*;

    use tempfile::tempdir;



    #[test]

    fn open_and_atomic_note() {

        let dir = tempdir().unwrap();

        let info = open_vault(dir.path()).unwrap();

        save_note(&info.root, "notes/hello.md", "# Hello\n").unwrap();

        let text = read_text(&info.root, "notes/hello.md").unwrap();

        assert!(text.contains("Hello"));

        assert!(info.root.join(".brainflow/vault.json").exists());

        assert!(info.root.join(".brainflow/bases/notes.base.json").exists());

    }



    #[test]

    fn rejects_path_escape() {

        let dir = tempdir().unwrap();

        let info = open_vault(dir.path()).unwrap();

        let err = resolve_in_vault(&info.root, "../outside.txt").unwrap_err();

        assert!(matches!(err, VaultError::PathEscape));

    }



    #[test]

    fn create_vault_fresh() {

        let dir = tempdir().unwrap();

        let path = dir.path().join("new-vault");

        let info = create_vault(&path, "Test").unwrap();

        assert!(info.root.join("notes").exists());

        assert!(info.root.join(".brainflow/templates/daily.md").exists());

    }



    #[test]

    fn note_stat_hash_changes() {

        let dir = tempdir().unwrap();

        let info = open_vault(dir.path()).unwrap();

        save_note(&info.root, "notes/s.md", "a").unwrap();

        let s1 = note_stat(&info.root, "notes/s.md").unwrap();

        save_note(&info.root, "notes/s.md", "b").unwrap();

        let s2 = note_stat(&info.root, "notes/s.md").unwrap();

        assert_ne!(s1.content_hash, s2.content_hash);

    }

}


