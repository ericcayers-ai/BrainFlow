//! Backlinks / outgoing links / tag index over analyzed notes.

use crate::explorer::list_note_paths;
use crate::markdown::{analyze_note, resolve_wikilink_target, Wikilink};
use crate::{read_text, VaultError};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkRef {
    pub from_path: String,
    pub to_path: Option<String>,
    pub to_target: String,
    pub raw: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NoteLinks {
    pub path: String,
    pub outgoing: Vec<LinkRef>,
    pub backlinks: Vec<LinkRef>,
    pub tags: Vec<String>,
    pub unresolved: Vec<Wikilink>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TagEntry {
    pub tag: String,
    pub paths: Vec<String>,
}

pub fn collect_all_links(root: &Path) -> Result<(Vec<LinkRef>, BTreeMap<String, Vec<String>>), VaultError> {
    let notes = list_note_paths(root)?;
    let mut links = Vec::new();
    let mut tag_map: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();

    for path in &notes {
        let content = match read_text(root, path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let analysis = analyze_note(path, &content);
        for t in &analysis.tags {
            tag_map.entry(t.clone()).or_default().insert(path.clone());
        }
        for wl in &analysis.wikilinks {
            let resolved = resolve_wikilink_target(&wl.target, &notes);
            links.push(LinkRef {
                from_path: path.clone(),
                to_path: resolved,
                to_target: wl.target.clone(),
                raw: wl.raw.clone(),
            });
        }
    }

    let tags = tag_map
        .into_iter()
        .map(|(tag, paths)| (tag, paths.into_iter().collect::<Vec<_>>()))
        .collect();
    Ok((links, tags))
}

pub fn links_for_note(root: &Path, note_path: &str) -> Result<NoteLinks, VaultError> {
    let (all_links, tag_map) = collect_all_links(root)?;
    let notes = list_note_paths(root)?;
    let content = read_text(root, note_path).unwrap_or_default();
    let analysis = analyze_note(note_path, &content);

    let outgoing: Vec<LinkRef> = all_links
        .iter()
        .filter(|l| l.from_path == note_path)
        .cloned()
        .collect();
    let backlinks: Vec<LinkRef> = all_links
        .iter()
        .filter(|l| l.to_path.as_deref() == Some(note_path))
        .cloned()
        .collect();
    let unresolved: Vec<Wikilink> = analysis
        .wikilinks
        .into_iter()
        .filter(|w| resolve_wikilink_target(&w.target, &notes).is_none())
        .collect();

    let mut tags = analysis.tags;
    if let Some(extra) = tag_map.get(note_path) {
        // tag_map is tag -> paths; we already have note tags
        let _ = extra;
    }
    tags.sort();
    tags.dedup();

    Ok(NoteLinks {
        path: note_path.to_string(),
        outgoing,
        backlinks,
        tags,
        unresolved,
    })
}

pub fn list_tags(root: &Path) -> Result<Vec<TagEntry>, VaultError> {
    let (_, tag_map) = collect_all_links(root)?;
    let mut out: Vec<TagEntry> = tag_map
        .into_iter()
        .map(|(tag, paths)| TagEntry { tag, paths })
        .collect();
    out.sort_by(|a, b| a.tag.cmp(&b.tag));
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{open_vault, save_note};
    use tempfile::tempdir;

    #[test]
    fn backlinks_resolve() {
        let dir = tempdir().unwrap();
        let info = open_vault(dir.path()).unwrap();
        save_note(&info.root, "notes/a.md", "# A\n\n[[b]]\n").unwrap();
        save_note(&info.root, "notes/b.md", "# B\n\n#topic\n").unwrap();
        let links = links_for_note(&info.root, "notes/b.md").unwrap();
        assert_eq!(links.backlinks.len(), 1);
        assert_eq!(links.backlinks[0].from_path, "notes/a.md");
        let tags = list_tags(&info.root).unwrap();
        assert!(tags.iter().any(|t| t.tag == "topic"));
    }
}
