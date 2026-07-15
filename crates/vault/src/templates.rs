//! Templates and daily-note stubs.

use crate::{atomic_write_text, ensure_layout, resolve_in_vault, VaultError};
use chrono::{Datelike, Local};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateInfo {
    pub id: String,
    pub path: String,
    pub name: String,
}

const DEFAULT_NOTE_TEMPLATE: &str = r#"---
tags: []
---
# {{title}}

"#;

const DEFAULT_DAILY_TEMPLATE: &str = r#"---
tags: [daily]
date: {{date}}
---
# {{date}}

## Focus

- 

## Notes

"#;

pub fn ensure_default_templates(root: &Path) -> Result<(), VaultError> {
    ensure_layout(root)?;
    let note = root.join(".brainflow/templates/note.md");
    if !note.exists() {
        atomic_write_text(&note, DEFAULT_NOTE_TEMPLATE)?;
    }
    let daily = root.join(".brainflow/templates/daily.md");
    if !daily.exists() {
        atomic_write_text(&daily, DEFAULT_DAILY_TEMPLATE)?;
    }
    Ok(())
}

pub fn list_templates(root: &Path) -> Result<Vec<TemplateInfo>, VaultError> {
    ensure_default_templates(root)?;
    let dir = root.join(".brainflow/templates");
    let mut out = Vec::new();
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("md") {
            continue;
        }
        let name = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("template")
            .to_string();
        let rel = format!(".brainflow/templates/{}.md", name);
        out.push(TemplateInfo {
            id: name.clone(),
            path: rel,
            name,
        });
    }
    out.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(out)
}

pub fn render_template(template: &str, title: &str, date: &str) -> String {
    template
        .replace("{{title}}", title)
        .replace("{{date}}", date)
}

pub fn apply_template(
    root: &Path,
    template_id: &str,
    dest_relative: &str,
    title: &str,
) -> Result<String, VaultError> {
    ensure_default_templates(root)?;
    let tpl_rel = format!(".brainflow/templates/{template_id}.md");
    let tpl_path = resolve_in_vault(root, &tpl_rel)?;
    let template = fs::read_to_string(tpl_path)?;
    let date = Local::now().format("%Y-%m-%d").to_string();
    let body = render_template(&template, title, &date);
    let dest = resolve_in_vault(root, dest_relative)?;
    if dest.exists() {
        return Err(VaultError::InvalidPath(format!(
            "already exists: {dest_relative}"
        )));
    }
    atomic_write_text(&dest, &body)?;
    Ok(body)
}

pub fn daily_note_path(root: &Path) -> Result<String, VaultError> {
    let now = Local::now();
    let folder = format!(
        "notes/daily/{:04}/{:02}",
        now.year(),
        now.month()
    );
    let _ = fs::create_dir_all(resolve_in_vault(root, &folder)?);
    Ok(format!("{folder}/{}.md", now.format("%Y-%m-%d")))
}

/// Create a unique Zettel-style note (`notes/YYYYMMDDHHmmss.md`) from the note template.
pub fn create_unique_note(root: &Path, title: Option<&str>) -> Result<(String, String), VaultError> {
    ensure_default_templates(root)?;
    let stamp = Local::now().format("%Y%m%d%H%M%S").to_string();
    let mut path = format!("notes/{stamp}.md");
    let mut n = 0u32;
    while resolve_in_vault(root, &path)?.exists() {
        n += 1;
        path = format!("notes/{stamp}-{n}.md");
    }
    let note_title = title
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .unwrap_or_else(|| stamp.clone());
    let body = apply_template(root, "note", &path, &note_title)?;
    Ok((path, body))
}

/// Pick a random Markdown note path from the vault (excluding `.brainflow`).
pub fn random_note_path(root: &Path) -> Result<Option<String>, VaultError> {
    use crate::explorer::list_note_paths;
    let notes = list_note_paths(root)?;
    let candidates: Vec<_> = notes
        .into_iter()
        .filter(|p| !p.replace('\\', "/").starts_with(".brainflow/"))
        .collect();
    if candidates.is_empty() {
        return Ok(None);
    }
    let idx = (now_entropy() as usize) % candidates.len();
    Ok(Some(candidates[idx].clone()))
}

fn now_entropy() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64 ^ d.as_millis() as u64)
        .unwrap_or(1)
}

pub fn open_or_create_daily_note(root: &Path) -> Result<(String, String), VaultError> {
    ensure_default_templates(root)?;
    let path = daily_note_path(root)?;
    let abs = resolve_in_vault(root, &path)?;
    if abs.exists() {
        return Ok((path, fs::read_to_string(abs)?));
    }
    let content = apply_template(root, "daily", &path, &Local::now().format("%Y-%m-%d").to_string())?;
    Ok((path, content))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::open_vault;
    use tempfile::tempdir;

    #[test]
    fn daily_note_creates_once() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        let (p1, c1) = open_or_create_daily_note(&info.root).unwrap();
        assert!(p1.contains("notes/daily/"));
        assert!(c1.contains("# "));
        let (p2, _) = open_or_create_daily_note(&info.root).unwrap();
        assert_eq!(p1, p2);
    }
}
