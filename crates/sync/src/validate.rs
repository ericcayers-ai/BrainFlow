//! Post-merge validation: workflow / vault schemas must pass before push.

use serde_json::Value;
use std::path::Path;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ValidateError {
    #[error("validation failed: {0}")]
    Failed(String),
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Debug, Clone)]
pub struct ValidateReport {
    pub ok: bool,
    pub errors: Vec<String>,
}

/// Walk `.brainflow/workflows/*.json` and require `schema_version == 1`.
pub fn validate_vault_workflows(vault: &Path) -> Result<ValidateReport, ValidateError> {
    let dir = vault.join(".brainflow/workflows");
    let mut errors = Vec::new();
    if dir.is_dir() {
        for entry in std::fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }
            let text = std::fs::read_to_string(&path)?;
            let doc: Value = serde_json::from_str(&text).map_err(|e| {
                ValidateError::Failed(format!("{}: {e}", path.display()))
            })?;
            match doc.get("schema_version").and_then(|v| v.as_u64()) {
                Some(1) => {}
                _ => errors.push(format!(
                    "{}: missing or unsupported schema_version (push blocked)",
                    path.strip_prefix(vault).unwrap_or(&path).display()
                )),
            }
        }
    }
    // Graphs: if present, require object root.
    let graphs = vault.join(".brainflow/graphs");
    if graphs.is_dir() {
        for entry in std::fs::read_dir(graphs)? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }
            let text = std::fs::read_to_string(&path)?;
            let doc: Value = match serde_json::from_str(&text) {
                Ok(v) => v,
                Err(e) => {
                    errors.push(format!("{}: {e}", path.display()));
                    continue;
                }
            };
            if !doc.is_object() && !doc.is_array() {
                errors.push(format!("{}: graph JSON must be object or array", path.display()));
            }
        }
    }
    Ok(ValidateReport {
        ok: errors.is_empty(),
        errors,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn blocks_invalid_workflow() {
        let dir = tempdir().unwrap();
        let wf = dir.path().join(".brainflow/workflows");
        std::fs::create_dir_all(&wf).unwrap();
        std::fs::write(wf.join("bad.json"), r#"{"title":"x"}"#).unwrap();
        let report = validate_vault_workflows(dir.path()).unwrap();
        assert!(!report.ok);
    }
}
