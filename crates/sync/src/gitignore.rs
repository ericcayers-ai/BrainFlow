//! BrainFlow vault `.gitignore` template.
//! Excludes indexes, embeddings, secrets, caches, machine settings, and temps.

/// Canonical BrainFlow ignore rules for portable vaults.
pub const BRAINFLOW_GITIGNORE: &str = r#"# BrainFlow — do not sync machine-local or secret data
# Indexes / catalogs (rebuildable; live under OS app-data when possible)
*.sqlite
*.sqlite-*
*.db
*.db-journal

# Embeddings / vector caches
.brainflow/local/
.brainflow/cache/
.brainflow/embeddings/
**/embeddings/

# Secrets and credential material (tokens live in OS credential store)
.env
.env.*
!.env.example
*.pem
*.key
secrets/
.credentials/

# Transient extraction / OCR / media work
.brainflow/tmp/
.brainflow/extract/
**/__pycache__/
*.tmp
*.temp
*.partial

# Machine settings / device ids
.brainflow/device.json
.brainflow/machine.json

# Transient run logs (portable run JSON under .brainflow/runs is OK)
.brainflow/logs/
*.log

# OS / editor junk
.DS_Store
Thumbs.db
desktop.ini
*.swp
*~
"#;

/// Write the BrainFlow `.gitignore` if missing, or merge missing critical lines.
pub fn ensure_brainflow_gitignore(vault_root: &std::path::Path) -> std::io::Result<()> {
    let path = vault_root.join(".gitignore");
    if !path.exists() {
        std::fs::write(&path, BRAINFLOW_GITIGNORE)?;
        return Ok(());
    }
    let existing = std::fs::read_to_string(&path)?;
    if existing.contains(".brainflow/local/") {
        return Ok(());
    }
    let mut merged = existing;
    if !merged.ends_with('\n') {
        merged.push('\n');
    }
    merged.push_str("\n# --- BrainFlow sync excludes ---\n");
    merged.push_str(BRAINFLOW_GITIGNORE);
    std::fs::write(&path, merged)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn writes_template() {
        let dir = tempdir().unwrap();
        ensure_brainflow_gitignore(dir.path()).unwrap();
        let text = std::fs::read_to_string(dir.path().join(".gitignore")).unwrap();
        assert!(text.contains(".brainflow/local/"));
        assert!(text.contains("*.sqlite"));
    }
}
