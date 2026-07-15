//! Frontmatter property updates and vault-wide schema suggestions.

use crate::explorer::list_note_paths;
use crate::markdown::{analyze_note, split_frontmatter};
use crate::{read_text, save_note, VaultError};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PropertySuggestion {
    pub key: String,
    pub count: usize,
    pub sample_values: Vec<String>,
}

/// Aggregate frontmatter keys across the vault for schema suggestions.
pub fn property_schema_suggestions(root: &Path) -> Result<Vec<PropertySuggestion>, VaultError> {
    let notes = list_note_paths(root)?;
    let mut counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut samples: BTreeMap<String, Vec<String>> = BTreeMap::new();

    for path in notes {
        let content = match read_text(root, &path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let analysis = analyze_note(&path, &content);
        if !analysis.frontmatter.tags.is_empty() {
            *counts.entry("tags".into()).or_default() += 1;
            let sample = analysis.frontmatter.tags.join(", ");
            push_sample(&mut samples, "tags", sample);
        }
        if !analysis.frontmatter.aliases.is_empty() {
            *counts.entry("aliases".into()).or_default() += 1;
            let sample = analysis.frontmatter.aliases.join(", ");
            push_sample(&mut samples, "aliases", sample);
        }
        for (k, v) in analysis.frontmatter.fields {
            *counts.entry(k.clone()).or_default() += 1;
            push_sample(&mut samples, &k, v);
        }
    }

    // Always suggest common Obsidian-ish keys even if unused.
    for key in ["tags", "aliases", "cssclasses", "status", "created", "updated"] {
        counts.entry(key.to_string()).or_insert(0);
    }

    let mut out: Vec<PropertySuggestion> = counts
        .into_iter()
        .map(|(key, count)| PropertySuggestion {
            sample_values: samples.remove(&key).unwrap_or_default(),
            key,
            count,
        })
        .collect();
    out.sort_by(|a, b| b.count.cmp(&a.count).then_with(|| a.key.cmp(&b.key)));
    Ok(out)
}

fn push_sample(map: &mut BTreeMap<String, Vec<String>>, key: &str, value: String) {
    if value.trim().is_empty() {
        return;
    }
    let list = map.entry(key.to_string()).or_default();
    if list.len() >= 5 || list.iter().any(|v| v == &value) {
        return;
    }
    list.push(value);
}

/// Set or replace a single frontmatter property; creates frontmatter if missing.
/// `tags` / `aliases` accept comma-separated lists. Returns updated full note content.
pub fn set_note_property(
    root: &Path,
    relative: &str,
    key: &str,
    value: &str,
) -> Result<String, VaultError> {
    let content = read_text(root, relative)?;
    let updated = upsert_frontmatter_field(&content, key, value);
    save_note(root, relative, &updated)?;
    Ok(updated)
}

pub fn upsert_frontmatter_field(content: &str, key: &str, value: &str) -> String {
    let (yaml_opt, body) = split_frontmatter(content);
    let key_norm = key.trim();
    if key_norm.is_empty() {
        return content.to_string();
    }

    let rendered = render_yaml_value(key_norm, value);
    let mut lines: Vec<String> = yaml_opt
        .unwrap_or("")
        .lines()
        .map(|l| l.to_string())
        .collect();

    let mut replaced = false;
    let mut i = 0;
    while i < lines.len() {
        let line = lines[i].clone();
        if let Some((k, _)) = line.split_once(':') {
            if k.trim() == key_norm {
                // Remove following list items belonging to this key.
                let mut end = i + 1;
                while end < lines.len()
                    && (lines[end].starts_with("  - ")
                        || lines[end].starts_with("- ")
                        || lines[end].starts_with('\t'))
                {
                    end += 1;
                }
                lines.splice(i..end, std::iter::once(rendered.clone()));
                replaced = true;
                break;
            }
        }
        i += 1;
    }
    if !replaced {
        lines.push(rendered);
    }

    let yaml = lines.join("\n").trim().to_string();
    if yaml.is_empty() {
        body.to_string()
    } else {
        format!("---\n{yaml}\n---\n{body}")
    }
}

fn render_yaml_value(key: &str, value: &str) -> String {
    let trimmed = value.trim();
    if matches!(key, "tags" | "aliases") {
        let parts: Vec<String> = trimmed
            .split(|c: char| c == ',' || c == ';')
            .map(|s| s.trim().trim_start_matches('#').to_string())
            .filter(|s| !s.is_empty())
            .collect();
        if parts.is_empty() {
            return format!("{key}: []");
        }
        return format!("{key}: [{}]", parts.join(", "));
    }
    if trimmed.is_empty() {
        return format!("{key}:");
    }
    if trimmed.contains(':') || trimmed.contains('#') || trimmed.contains('"') {
        let escaped = trimmed.replace('\\', "\\\\").replace('"', "\\\"");
        return format!("{key}: \"{escaped}\"");
    }
    format!("{key}: {trimmed}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{open_vault, save_note};
    use tempfile::tempdir;

    #[test]
    fn upsert_and_suggestions() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        save_note(
            &info.root,
            "notes/a.md",
            "---\ntags: [alpha]\nstatus: draft\n---\n# A\n",
        )
        .unwrap();
        save_note(
            &info.root,
            "notes/b.md",
            "---\nstatus: done\n---\n# B\n",
        )
        .unwrap();

        let updated = set_note_property(&info.root, "notes/a.md", "status", "published").unwrap();
        assert!(updated.contains("status: published"));
        assert!(updated.contains("tags: [alpha]"));

        let suggestions = property_schema_suggestions(&info.root).unwrap();
        assert!(suggestions.iter().any(|s| s.key == "status" && s.count >= 1));
        assert!(suggestions.iter().any(|s| s.key == "tags"));
    }
}
