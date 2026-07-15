//! Frontmatter, wikilinks, tags, and basic Markdown note analysis.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::sync::OnceLock;

#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq, Eq)]
pub struct Frontmatter {
    /// Parsed YAML-ish key/value pairs (string values only for v1 basics).
    pub fields: Vec<(String, String)>,
    pub aliases: Vec<String>,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Wikilink {
    pub target: String,
    pub alias: Option<String>,
    pub heading: Option<String>,
    pub block: Option<String>,
    pub raw: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NoteAnalysis {
    pub frontmatter: Frontmatter,
    pub body: String,
    pub wikilinks: Vec<Wikilink>,
    pub tags: Vec<String>,
    pub title_guess: String,
}

fn wikilink_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\[\[([^\[\]]+)\]\]").expect("wikilink regex"))
}

fn inline_tag_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?:^|[\s(])#([A-Za-z0-9_][A-Za-z0-9_/\-]*)").expect("tag regex"))
}

/// Split optional YAML frontmatter (`---` … `---`) from the body.
pub fn split_frontmatter(content: &str) -> (Option<&str>, &str) {
    let trimmed = content.trim_start_matches('\u{feff}');
    if !trimmed.starts_with("---") {
        return (None, content);
    }
    let after = &trimmed[3..];
    let after = after.strip_prefix('\r').unwrap_or(after);
    let after = after.strip_prefix('\n').unwrap_or(after);
    if let Some(end) = after.find("\n---") {
        let yaml = &after[..end];
        let rest = &after[end + 4..];
        let rest = rest.strip_prefix('\r').unwrap_or(rest);
        let rest = rest.strip_prefix('\n').unwrap_or(rest);
        return (Some(yaml), rest);
    }
    (None, content)
}

/// Very small YAML subset: `key: value`, `tags: [a, b]`, `aliases: [x]`, and `tags:` lists.
pub fn parse_frontmatter_yaml(yaml: &str) -> Frontmatter {
    let mut fm = Frontmatter::default();
    let mut list_key: Option<&str> = None;
    for raw_line in yaml.lines() {
        let line = raw_line.trim_end();
        if line.trim().is_empty() || line.trim_start().starts_with('#') {
            continue;
        }
        if let Some(rest) = line.strip_prefix("  - ").or_else(|| line.strip_prefix("- ")) {
            if let Some(key) = list_key {
                let item = unquote(rest.trim());
                match key {
                    "tags" | "tag" => fm.tags.push(normalize_tag(&item)),
                    "aliases" | "alias" => fm.aliases.push(item),
                    other => fm.fields.push((other.to_string(), item)),
                }
            }
            continue;
        }
        list_key = None;
        if let Some((k, v)) = line.split_once(':') {
            let key = k.trim();
            let val = v.trim();
            if val.is_empty() {
                list_key = Some(key);
                continue;
            }
            if val.starts_with('[') && val.ends_with(']') {
                let inner = &val[1..val.len() - 1];
                for part in inner.split(',') {
                    let item = unquote(part.trim());
                    if item.is_empty() {
                        continue;
                    }
                    match key {
                        "tags" | "tag" => fm.tags.push(normalize_tag(&item)),
                        "aliases" | "alias" => fm.aliases.push(item),
                        _ => fm.fields.push((key.to_string(), item)),
                    }
                }
            } else {
                let item = unquote(val);
                match key {
                    "tags" | "tag" => {
                        for t in item.split(|c: char| c == ',' || c.is_whitespace()) {
                            if !t.is_empty() {
                                fm.tags.push(normalize_tag(t));
                            }
                        }
                    }
                    "aliases" | "alias" => fm.aliases.push(item),
                    _ => fm.fields.push((key.to_string(), item)),
                }
            }
        }
    }
    fm.tags.sort();
    fm.tags.dedup();
    fm.aliases.sort();
    fm.aliases.dedup();
    fm
}

fn unquote(s: &str) -> String {
    let s = s.trim();
    if (s.starts_with('"') && s.ends_with('"')) || (s.starts_with('\'') && s.ends_with('\'')) {
        s[1..s.len() - 1].to_string()
    } else {
        s.to_string()
    }
}

pub fn normalize_tag(tag: &str) -> String {
    tag.trim()
        .trim_start_matches('#')
        .trim()
        .to_ascii_lowercase()
}

pub fn parse_wikilink_inner(inner: &str) -> Wikilink {
    let raw = format!("[[{inner}]]");
    let (target_part, alias) = match inner.split_once('|') {
        Some((t, a)) => (t.trim(), Some(a.trim().to_string())),
        None => (inner.trim(), None),
    };
    let (target, heading, block) = if let Some((t, rest)) = target_part.split_once('#') {
        if let Some(block) = rest.strip_prefix('^') {
            (t.trim().to_string(), None, Some(block.trim().to_string()))
        } else if let Some((h, b)) = rest.split_once("#^") {
            (
                t.trim().to_string(),
                Some(h.trim().to_string()),
                Some(b.trim().to_string()),
            )
        } else {
            (t.trim().to_string(), Some(rest.trim().to_string()), None)
        }
    } else {
        (target_part.to_string(), None, None)
    };
    Wikilink {
        target,
        alias,
        heading,
        block,
        raw,
    }
}

pub fn extract_wikilinks(body: &str) -> Vec<Wikilink> {
    wikilink_re()
        .captures_iter(body)
        .filter_map(|c| c.get(1).map(|m| parse_wikilink_inner(m.as_str())))
        .collect()
}

/// True when a wikilink target (possibly with `#heading` / `#^block`) matches any of `candidates`
/// (note stem, relative path, or path with `.md`).
pub fn wikilink_matching_target(target_part: &str, candidates: &[String]) -> bool {
    let target_core = target_part
        .split_once('#')
        .map(|(t, _)| t.trim())
        .unwrap_or(target_part.trim());
    let lower = target_core.replace('\\', "/").to_ascii_lowercase();
    let lower_md = if lower.ends_with(".md") {
        lower.clone()
    } else {
        format!("{lower}.md")
    };
    for c in candidates {
        let cand = c.replace('\\', "/").to_ascii_lowercase();
        let cand_stem = PathStem(cand.as_str()).stem().to_ascii_lowercase();
        if lower == cand
            || lower_md == cand
            || lower == cand_stem
            || lower.trim_end_matches(".md") == cand.trim_end_matches(".md")
        {
            return true;
        }
    }
    false
}

struct PathStem<'a>(&'a str);
impl PathStem<'_> {
    fn stem(&self) -> &str {
        let s = self.0.rsplit('/').next().unwrap_or(self.0);
        s.strip_suffix(".md").unwrap_or(s)
    }
}

pub fn extract_inline_tags(body: &str) -> Vec<String> {
    let mut tags: BTreeSet<String> = BTreeSet::new();
    for c in inline_tag_re().captures_iter(body) {
        if let Some(t) = c.get(1) {
            tags.insert(normalize_tag(t.as_str()));
        }
    }
    tags.into_iter().collect()
}

pub fn guess_title(path: &str, body: &str) -> String {
    for line in body.lines() {
        let t = line.trim();
        if let Some(rest) = t.strip_prefix("# ") {
            let title = rest.trim();
            if !title.is_empty() {
                return title.to_string();
            }
        }
    }
    std::path::Path::new(path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(path)
        .to_string()
}

pub fn analyze_note(path: &str, content: &str) -> NoteAnalysis {
    let (yaml, body) = split_frontmatter(content);
    let frontmatter = yaml.map(parse_frontmatter_yaml).unwrap_or_default();
    let wikilinks = extract_wikilinks(body);
    let mut tags: BTreeSet<String> = frontmatter.tags.iter().cloned().collect();
    for t in extract_inline_tags(body) {
        tags.insert(t);
    }
    let tags: Vec<String> = tags.into_iter().collect();
    let title_guess = guess_title(path, body);
    NoteAnalysis {
        frontmatter,
        body: body.to_string(),
        wikilinks,
        tags,
        title_guess,
    }
}

/// Resolve a wikilink target against known note paths (stem or relative path, case-insensitive).
pub fn resolve_wikilink_target(target: &str, note_paths: &[String]) -> Option<String> {
    let target = target.trim().replace('\\', "/");
    let target_lower = target.to_ascii_lowercase();
    let with_md = if target_lower.ends_with(".md") {
        target_lower.clone()
    } else {
        format!("{target_lower}.md")
    };

    for p in note_paths {
        let norm = p.replace('\\', "/");
        let lower = norm.to_ascii_lowercase();
        if lower == target_lower || lower == with_md {
            return Some(norm);
        }
        if let Some(stem) = std::path::Path::new(&lower).file_stem() {
            if stem.to_string_lossy() == target_lower.trim_end_matches(".md") {
                return Some(norm);
            }
        }
        if lower.ends_with(&format!("/{with_md}")) || lower.ends_with(&with_md) {
            return Some(norm);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_frontmatter_tags_and_aliases() {
        let content = r#"---
title: Hello
tags: [study, plan]
aliases:
  - Intro
---
# Hello

See [[Other Note|alt]] and #inbox
"#;
        let a = analyze_note("notes/hello.md", content);
        assert_eq!(a.frontmatter.aliases, vec!["Intro".to_string()]);
        assert!(a.tags.contains(&"study".into()));
        assert!(a.tags.contains(&"plan".into()));
        assert!(a.tags.contains(&"inbox".into()));
        assert_eq!(a.wikilinks.len(), 1);
        assert_eq!(a.wikilinks[0].target, "Other Note");
        assert_eq!(a.wikilinks[0].alias.as_deref(), Some("alt"));
        assert_eq!(a.title_guess, "Hello");
    }

    #[test]
    fn resolves_wikilink_by_stem() {
        let notes = vec![
            "notes/Other Note.md".into(),
            "notes/hello.md".into(),
        ];
        assert_eq!(
            resolve_wikilink_target("Other Note", &notes).as_deref(),
            Some("notes/Other Note.md")
        );
    }
}
