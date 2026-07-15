//! Portable canvas JSON read/write (JSON Canvas–inspired).

use crate::{atomic_write_json, resolve_in_vault, VaultError};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CanvasDoc {
    pub schema_version: u32,
    pub kind: String,
    pub id: String,
    #[serde(default)]
    pub nodes: Vec<CanvasNode>,
    #[serde(default)]
    pub edges: Vec<CanvasEdge>,
    #[serde(default)]
    pub note: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CanvasNode {
    pub id: String,
    #[serde(rename = "type")]
    pub node_type: String,
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
    #[serde(default)]
    pub text: Option<String>,
    #[serde(default)]
    pub file: Option<String>,
    #[serde(default)]
    pub color: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CanvasEdge {
    pub id: String,
    pub from_node: String,
    pub to_node: String,
    #[serde(default)]
    pub label: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CanvasListItem {
    pub path: String,
    pub id: String,
    pub title: String,
}

fn canvas_dir(root: &Path) -> std::path::PathBuf {
    root.join(".brainflow/graphs/canvas")
}

pub fn list_canvases(root: &Path) -> Result<Vec<CanvasListItem>, VaultError> {
    let dir = canvas_dir(root);
    if !dir.exists() {
        return Ok(vec![]);
    }
    let mut out = Vec::new();
    for entry in fs::read_dir(&dir)? {
        let entry = entry?;
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if !name.ends_with(".canvas.json") && !name.ends_with(".json") {
            continue;
        }
        let rel = format!(".brainflow/graphs/canvas/{name}");
        let (id, title) = match fs::read_to_string(&path) {
            Ok(text) => match serde_json::from_str::<Value>(&text) {
                Ok(v) => (
                    v.get("id")
                        .and_then(|x| x.as_str())
                        .unwrap_or("canvas")
                        .to_string(),
                    v.get("note")
                        .and_then(|x| x.as_str())
                        .or_else(|| v.get("id").and_then(|x| x.as_str()))
                        .unwrap_or(&name)
                        .to_string(),
                ),
                Err(_) => (name.clone(), name.clone()),
            },
            Err(_) => (name.clone(), name.clone()),
        };
        out.push(CanvasListItem {
            path: rel,
            id,
            title,
        });
    }
    out.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(out)
}

pub fn read_canvas(root: &Path, relative: &str) -> Result<CanvasDoc, VaultError> {
    let path = resolve_in_vault(root, relative)?;
    let text = fs::read_to_string(&path)?;
    let doc: CanvasDoc = serde_json::from_str(&text)?;
    Ok(doc)
}

pub fn write_canvas(root: &Path, relative: &str, doc: &CanvasDoc) -> Result<(), VaultError> {
    let path = resolve_in_vault(root, relative)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    atomic_write_json(&path, doc)
}

/// Import raw bytes into the vault (atomic). Returns the relative destination path.
pub fn import_file_bytes(
    root: &Path,
    dest_relative: &str,
    bytes: &[u8],
) -> Result<String, VaultError> {
    use std::io::Write;
    let rel = dest_relative.replace('\\', "/");
    let path = resolve_in_vault(root, &rel)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension(format!(
        "tmp-{}-{}",
        std::process::id(),
        uuid::Uuid::new_v4()
    ));
    {
        let mut f = fs::File::create(&tmp)?;
        f.write_all(bytes)?;
        f.sync_all()?;
    }
    fs::rename(&tmp, &path)?;
    Ok(rel)
}

pub fn import_text_file(
    root: &Path,
    dest_relative: &str,
    content: &str,
) -> Result<String, VaultError> {
    let rel = dest_relative.replace('\\', "/");
    let path = resolve_in_vault(root, &rel)?;
    crate::atomic_write_text(&path, content)?;
    Ok(rel)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::foundations::ensure_bases_canvas_foundations;
    use crate::open_vault;
    use tempfile::tempdir;

    #[test]
    fn canvas_roundtrip() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        ensure_bases_canvas_foundations(&info.root).unwrap();
        let list = list_canvases(&info.root).unwrap();
        assert!(!list.is_empty());
        let path = &list[0].path;
        let mut doc = read_canvas(&info.root, path).unwrap();
        doc.nodes.push(CanvasNode {
            id: "n2".into(),
            node_type: "text".into(),
            x: 40.0,
            y: 60.0,
            width: 200.0,
            height: 80.0,
            text: Some("Hello".into()),
            file: None,
            color: None,
        });
        write_canvas(&info.root, path, &doc).unwrap();
        let again = read_canvas(&info.root, path).unwrap();
        assert!(again.nodes.iter().any(|n| n.id == "n2"));
    }

    #[test]
    fn import_markdown() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        let rel = import_text_file(&info.root, "notes/dropped.md", "# Dropped\n").unwrap();
        assert_eq!(rel, "notes/dropped.md");
        assert!(info.root.join("notes/dropped.md").exists());
    }
}
