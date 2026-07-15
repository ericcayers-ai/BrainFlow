//! Rename notes and rewrite wikilinks / embeds across the vault.

use crate::explorer::list_note_paths;
use crate::markdown::wikilink_matching_target;
use crate::{read_text, resolve_in_vault, save_note, VaultError};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::sync::OnceLock;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RenameResult {
    pub from_path: String,
    pub to_path: String,
    pub notes_updated: usize,
    pub links_rewritten: usize,
}

fn normalize_rel(p: &str) -> String {
    p.replace('\\', "/")
}

fn stem_of(path: &str) -> String {
    let norm = normalize_rel(path);
    Path::new(&norm)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(&norm)
        .to_string()
}

fn wiki_or_embed_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(!?)\[\[([^\[\]]+)\]\]").expect("embed/wikilink regex"))
}

fn rewrite_wikilink_inner(inner: &str, old_stems: &[String], new_stem: &str) -> Option<String> {
    let (target_part, alias) = match inner.split_once('|') {
        Some((t, a)) => (t.trim(), Some(a.trim())),
        None => (inner.trim(), None),
    };
    if !wikilink_matching_target(target_part, old_stems) {
        return None;
    }
    let suffix = if let Some((_, rest)) = target_part.split_once('#') {
        format!("#{rest}")
    } else {
        String::new()
    };
    let mut rebuilt = format!("{new_stem}{suffix}");
    if let Some(a) = alias {
        rebuilt.push('|');
        rebuilt.push_str(a);
    }
    Some(rebuilt)
}

fn rewrite_body(body: &str, old_stems: &[String], new_stem: &str) -> (String, usize) {
    let mut count = 0usize;
    let out = wiki_or_embed_re()
        .replace_all(body, |caps: &regex::Captures| {
            let bang = caps.get(1).map(|m| m.as_str()).unwrap_or("");
            let inner = caps.get(2).map(|m| m.as_str()).unwrap_or("");
            if let Some(rewritten) = rewrite_wikilink_inner(inner, old_stems, new_stem) {
                count += 1;
                format!("{bang}[[{rewritten}]]")
            } else {
                caps.get(0).map(|m| m.as_str().to_string()).unwrap_or_default()
            }
        })
        .into_owned();
    (out, count)
}

/// Rename a Markdown note and rewrite wikilinks/embeds that pointed at the old stem/path.
pub fn rename_note(
    root: &Path,
    from_relative: &str,
    to_relative: &str,
) -> Result<RenameResult, VaultError> {
    let from = normalize_rel(from_relative);
    let to = normalize_rel(to_relative);
    if !to.to_ascii_lowercase().ends_with(".md") {
        return Err(VaultError::InvalidPath(
            "rename destination must be a .md note".into(),
        ));
    }
    let from_path = resolve_in_vault(root, &from)?;
    let to_path = resolve_in_vault(root, &to)?;
    if !from_path.exists() {
        return Err(VaultError::InvalidPath(format!("note not found: {from}")));
    }
    if to_path.exists() {
        return Err(VaultError::InvalidPath(format!(
            "destination already exists: {to}"
        )));
    }
    if let Some(parent) = to_path.parent() {
        fs::create_dir_all(parent)?;
    }

    let old_stem = stem_of(&from);
    let new_stem = stem_of(&to);
    let old_path_no_ext = from
        .trim_end_matches(".md")
        .trim_end_matches(".MD")
        .to_string();
    let old_stems = vec![
        old_stem.clone(),
        old_path_no_ext.clone(),
        from.clone(),
        format!("{old_stem}.md"),
    ];

    fs::rename(&from_path, &to_path)?;

    let notes = list_note_paths(root)?;
    let mut notes_updated = 0usize;
    let mut links_rewritten = 0usize;

    for note in &notes {
        let norm = normalize_rel(note);
        let content = match read_text(root, &norm) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let (new_body, n) = rewrite_body(&content, &old_stems, &new_stem);
        if n > 0 && new_body != content {
            save_note(root, &norm, &new_body)?;
            notes_updated += 1;
            links_rewritten += n;
        }
    }

    Ok(RenameResult {
        from_path: from,
        to_path: to,
        notes_updated,
        links_rewritten,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{open_vault, save_note};
    use tempfile::tempdir;

    #[test]
    fn renames_and_rewrites_wikilinks() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        save_note(&info.root, "notes/Alpha.md", "# Alpha\n").unwrap();
        save_note(
            &info.root,
            "notes/Beta.md",
            "See [[Alpha]] and ![[Alpha#Intro]] and [[Alpha|label]].\n",
        )
        .unwrap();

        let res = rename_note(&info.root, "notes/Alpha.md", "notes/Gamma.md").unwrap();
        assert_eq!(res.to_path, "notes/Gamma.md");
        assert!(res.links_rewritten >= 3);

        let beta = read_text(&info.root, "notes/Beta.md").unwrap();
        assert!(beta.contains("[[Gamma]]"));
        assert!(beta.contains("![[Gamma#Intro]]"));
        assert!(beta.contains("[[Gamma|label]]"));
        assert!(!beta.contains("[[Alpha]]"));
        assert!(info.root.join("notes/Gamma.md").exists());
        assert!(!info.root.join("notes/Alpha.md").exists());
    }
}
