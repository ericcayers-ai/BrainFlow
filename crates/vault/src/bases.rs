//! Bases: filterable/sortable table rows over note properties.

use crate::explorer::list_note_paths;
use crate::markdown::analyze_note;
use crate::{note_stat, read_text, VaultError};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BaseDefinition {
    pub schema_version: u32,
    pub kind: String,
    pub id: String,
    pub title: String,
    pub source: String,
    pub columns: Vec<String>,
    #[serde(default)]
    pub filters: Vec<BaseFilter>,
    #[serde(default)]
    pub sort: Vec<BaseSort>,
    #[serde(default)]
    pub formulas: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BaseFilter {
    pub column: String,
    pub op: String,
    pub value: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BaseSort {
    pub column: String,
    pub direction: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BaseRow {
    pub path: String,
    pub title: String,
    pub tags: Vec<String>,
    pub aliases: Vec<String>,
    pub updated_at: Option<u64>,
    pub size: Option<u64>,
    pub fields: Vec<(String, String)>,
    /// Evaluated formula columns keyed by formula name.
    #[serde(default)]
    pub formula_values: Vec<(String, String)>,
}

fn normalize_rel(p: &str) -> String {
    p.replace('\\', "/")
}

/// Load a portable `.base.json` definition (or return the default notes base).
pub fn load_base(root: &Path, relative: Option<&str>) -> Result<BaseDefinition, VaultError> {
    let rel = relative.unwrap_or(".brainflow/bases/notes.base.json");
    let path = root.join(rel);
    if !path.exists() {
        return Ok(BaseDefinition {
            schema_version: 1,
            kind: "base".into(),
            id: "notes".into(),
            title: "Notes".into(),
            source: "vault_notes".into(),
            columns: vec![
                "path".into(),
                "title".into(),
                "tags".into(),
                "updated_at".into(),
            ],
            filters: vec![],
            sort: vec![BaseSort {
                column: "path".into(),
                direction: "asc".into(),
            }],
            formulas: json!({}),
        });
    }
    let text = fs::read_to_string(&path)?;
    let mut def: BaseDefinition = serde_json::from_str(&text)?;
    if def.columns.is_empty() {
        def.columns = vec![
            "path".into(),
            "title".into(),
            "tags".into(),
            "updated_at".into(),
        ];
    }
    Ok(def)
}

pub fn save_base(root: &Path, relative: &str, def: &BaseDefinition) -> Result<(), VaultError> {
    let path = root.join(relative);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    crate::atomic_write_json(&path, def)
}

fn row_matches(row: &BaseRow, filters: &[BaseFilter]) -> bool {
    for f in filters {
        let cell = cell_value(row, &f.column).to_ascii_lowercase();
        let val = f.value.to_ascii_lowercase();
        let ok = match f.op.as_str() {
            "contains" | "includes" => cell.contains(&val),
            "eq" | "equals" => cell == val,
            "starts_with" => cell.starts_with(&val),
            "ne" | "not" => cell != val,
            _ => cell.contains(&val),
        };
        if !ok {
            return false;
        }
    }
    true
}

fn cell_value(row: &BaseRow, column: &str) -> String {
    match column {
        "path" => row.path.clone(),
        "title" => row.title.clone(),
        "tags" => row.tags.join(", "),
        "aliases" => row.aliases.join(", "),
        "updated_at" => row
            .updated_at
            .map(|u| u.to_string())
            .unwrap_or_default(),
        "size" => row.size.map(|u| u.to_string()).unwrap_or_default(),
        other => row
            .formula_values
            .iter()
            .find(|(k, _)| k.eq_ignore_ascii_case(other))
            .map(|(_, v)| v.clone())
            .or_else(|| {
                row.fields
                    .iter()
                    .find(|(k, _)| k.eq_ignore_ascii_case(other))
                    .map(|(_, v)| v.clone())
            })
            .unwrap_or_default(),
    }
}

/// Evaluate a small formula DSL over a row.
/// Supported: `len(tags)`, `len(aliases)`, `word_count`, `contains(tags,"x")`,
/// `field("status")`, `upper(title)`, `lower(title)`, literals.
pub fn eval_formula(expr: &str, row: &BaseRow, body_word_count: usize) -> String {
    let e = expr.trim();
    if e.is_empty() {
        return String::new();
    }
    if let Some(inner) = strip_call(e, "len") {
        return match inner.trim() {
            "tags" => row.tags.len().to_string(),
            "aliases" => row.aliases.len().to_string(),
            "fields" => row.fields.len().to_string(),
            other => cell_value(row, other).len().to_string(),
        };
    }
    if e.eq_ignore_ascii_case("word_count") {
        return body_word_count.to_string();
    }
    if let Some(inner) = strip_call(e, "contains") {
        let (hay, needle) = split_two_args(inner);
        let hay_v = match hay.trim() {
            "tags" => row.tags.join(", "),
            "aliases" => row.aliases.join(", "),
            other => cell_value(row, other),
        };
        let needle_v = unquote_arg(needle);
        return hay_v
            .to_ascii_lowercase()
            .contains(&needle_v.to_ascii_lowercase())
            .to_string();
    }
    if let Some(inner) = strip_call(e, "field") {
        return cell_value(row, &unquote_arg(inner));
    }
    if let Some(inner) = strip_call(e, "upper") {
        return cell_value(row, &unquote_arg(inner)).to_ascii_uppercase();
    }
    if let Some(inner) = strip_call(e, "lower") {
        return cell_value(row, &unquote_arg(inner)).to_ascii_lowercase();
    }
    // Bare column reference
    let v = cell_value(row, e);
    if !v.is_empty() {
        return v;
    }
    unquote_arg(e)
}

fn strip_call<'a>(expr: &'a str, name: &str) -> Option<&'a str> {
    let lower = expr.to_ascii_lowercase();
    let prefix = format!("{}(", name.to_ascii_lowercase());
    if lower.starts_with(&prefix) && expr.ends_with(')') {
        Some(&expr[prefix.len()..expr.len() - 1])
    } else {
        None
    }
}

fn split_two_args(inner: &str) -> (&str, &str) {
    if let Some((a, b)) = inner.split_once(',') {
        (a, b)
    } else {
        (inner, "")
    }
}

fn unquote_arg(s: &str) -> String {
    let t = s.trim();
    if (t.starts_with('"') && t.ends_with('"')) || (t.starts_with('\'') && t.ends_with('\'')) {
        t[1..t.len() - 1].to_string()
    } else {
        t.to_string()
    }
}

fn apply_formulas(row: &mut BaseRow, formulas: &Value, body_word_count: usize) {
    let Some(obj) = formulas.as_object() else {
        return;
    };
    let mut values = Vec::new();
    for (name, expr) in obj {
        let expr_s = expr.as_str().unwrap_or("").to_string();
        values.push((name.clone(), eval_formula(&expr_s, row, body_word_count)));
    }
    row.formula_values = values;
}

fn count_words(body: &str) -> usize {
    body.split_whitespace().filter(|w| !w.is_empty()).count()
}

fn compare_rows(a: &BaseRow, b: &BaseRow, sort: &[BaseSort]) -> std::cmp::Ordering {
    use std::cmp::Ordering;
    for s in sort {
        let av = cell_value(a, &s.column);
        let bv = cell_value(b, &s.column);
        let ord = if s.column == "updated_at" || s.column == "size" {
            let an: u64 = av.parse().unwrap_or(0);
            let bn: u64 = bv.parse().unwrap_or(0);
            an.cmp(&bn)
        } else {
            av.to_ascii_lowercase()
                .cmp(&bv.to_ascii_lowercase())
        };
        if ord != Ordering::Equal {
            return if s.direction.eq_ignore_ascii_case("desc") {
                ord.reverse()
            } else {
                ord
            };
        }
    }
    Ordering::Equal
}

/// Build table rows for the notes base (optionally applying filters/sorts from the definition
/// plus caller overrides).
pub fn base_rows(
    root: &Path,
    relative_base: Option<&str>,
    filter_override: Option<&[BaseFilter]>,
    sort_override: Option<&[BaseSort]>,
) -> Result<(BaseDefinition, Vec<BaseRow>), VaultError> {
    let mut def = load_base(root, relative_base)?;
    let filters = filter_override.unwrap_or(&def.filters);
    let sorts = sort_override.unwrap_or(&def.sort);

    let notes = list_note_paths(root)?;
    let mut rows = Vec::with_capacity(notes.len());
    for path in notes {
        let norm = normalize_rel(&path);
        let content = match read_text(root, &norm) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let analysis = analyze_note(&norm, &content);
        let stat = note_stat(root, &norm).ok();
        let word_count = count_words(&analysis.body);
        let mut row = BaseRow {
            path: norm,
            title: analysis.title_guess,
            tags: analysis.tags,
            aliases: analysis.frontmatter.aliases,
            updated_at: stat.as_ref().and_then(|s| s.modified_ms),
            size: stat.as_ref().and_then(|s| s.size),
            fields: analysis.frontmatter.fields,
            formula_values: vec![],
        };
        apply_formulas(&mut row, &def.formulas, word_count);
        if row_matches(&row, filters) {
            rows.push(row);
        }
    }
    rows.sort_by(|a, b| compare_rows(a, b, sorts));
    // Persist applied overrides into returned definition for UI convenience.
    if let Some(f) = filter_override {
        def.filters = f.to_vec();
    }
    if let Some(s) = sort_override {
        def.sort = s.to_vec();
    }
    Ok((def, rows))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{open_vault, save_note};
    use tempfile::tempdir;

    #[test]
    fn rows_filter_and_sort() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        save_note(
            &info.root,
            "notes/a.md",
            "---\ntags: [alpha]\n---\n# A\n",
        )
        .unwrap();
        save_note(
            &info.root,
            "notes/b.md",
            "---\ntags: [beta]\n---\n# B\n",
        )
        .unwrap();

        let filters = vec![BaseFilter {
            column: "tags".into(),
            op: "contains".into(),
            value: "alpha".into(),
        }];
        let (_, rows) = base_rows(&info.root, None, Some(&filters), None).unwrap();
        assert_eq!(rows.len(), 1);
        assert!(rows[0].path.ends_with("a.md"));
    }

    #[test]
    fn formula_len_tags() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        save_note(
            &info.root,
            "notes/a.md",
            "---\ntags: [alpha, beta]\n---\n# A\n\nhello world\n",
        )
        .unwrap();
        let mut def = load_base(&info.root, None).unwrap();
        def.formulas = json!({
            "tag_count": "len(tags)",
            "words": "word_count"
        });
        save_base(&info.root, ".brainflow/bases/notes.base.json", &def).unwrap();
        let (_, rows) = base_rows(&info.root, None, None, None).unwrap();
        let row = rows.iter().find(|r| r.path.ends_with("a.md")).unwrap();
        let tag_count = row
            .formula_values
            .iter()
            .find(|(k, _)| k == "tag_count")
            .map(|(_, v)| v.as_str());
        assert_eq!(tag_count, Some("2"));
        let words = row
            .formula_values
            .iter()
            .find(|(k, _)| k == "words")
            .map(|(_, v)| v.as_str());
        // "# A" + "hello world" → four whitespace tokens
        assert_eq!(words, Some("4"));
    }
}
