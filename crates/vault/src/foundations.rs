//! Portable Bases / Canvas foundation stubs under `.brainflow/`.

use crate::{atomic_write_json, ensure_layout, VaultError};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FoundationPaths {
    pub bases_dir: String,
    pub canvas_dir: String,
    pub sample_base: String,
    pub sample_canvas: String,
}

/// Ensure `.brainflow/bases` and `.brainflow/graphs/canvas` exist with sample stubs.
pub fn ensure_bases_canvas_foundations(root: &Path) -> Result<FoundationPaths, VaultError> {
    ensure_layout(root)?;
    let bases = root.join(".brainflow/bases");
    let canvas = root.join(".brainflow/graphs/canvas");
    fs::create_dir_all(&bases)?;
    fs::create_dir_all(&canvas)?;

    let sample_base = bases.join("notes.base.json");
    if !sample_base.exists() {
        let stub = json!({
            "schema_version": 1,
            "kind": "base",
            "id": "notes",
            "title": "Notes",
            "source": "vault_notes",
            "columns": ["path", "title", "tags", "updated_at"],
            "filters": [],
            "sort": [{ "column": "path", "direction": "asc" }],
            "formulas": {
              "tag_count": "len(tags)",
              "words": "word_count"
            },
            "note": "Portable Bases definition; desktop UI reads note properties via base_rows."
        });
        atomic_write_json(&sample_base, &stub)?;
    }

    let sample_canvas = canvas.join("welcome.canvas.json");
    if !sample_canvas.exists() {
        // JSON Canvas–inspired minimal stub (not claiming full interop yet).
        let stub = json!({
            "schema_version": 1,
            "kind": "canvas",
            "id": "welcome",
            "nodes": [
                {
                    "id": "n1",
                    "type": "text",
                    "x": 0,
                    "y": 0,
                    "width": 280,
                    "height": 120,
                    "text": "Welcome canvas — drag nodes in the Canvas panel"
                }
            ],
            "edges": [],
            "note": "Portable canvas JSON under .brainflow/graphs/canvas"
        });
        atomic_write_json(&sample_canvas, &stub)?;
    }

    Ok(FoundationPaths {
        bases_dir: ".brainflow/bases".into(),
        canvas_dir: ".brainflow/graphs/canvas".into(),
        sample_base: ".brainflow/bases/notes.base.json".into(),
        sample_canvas: ".brainflow/graphs/canvas/welcome.canvas.json".into(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::open_vault;
    use tempfile::tempdir;

    #[test]
    fn writes_stubs() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        let paths = ensure_bases_canvas_foundations(&info.root).unwrap();
        assert!(info.root.join(&paths.sample_base).exists());
        assert!(info.root.join(&paths.sample_canvas).exists());
    }
}
