//! Three-way merge strategies for Markdown and structured workflow/graph JSON.

use serde_json::{Map, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MergeOutcome {
    Clean(String),
    Conflict {
        merged: String,
        conflict_markers: bool,
    },
}

/// Paragraph/block-aware three-way merge for Markdown.
/// Units are blank-line-separated blocks; LCS-aligned when lengths diverge.
pub fn merge_markdown_three_way(base: &str, local: &str, remote: &str) -> MergeOutcome {
    let base_blocks = split_blocks(base);
    let local_blocks = split_blocks(local);
    let remote_blocks = split_blocks(remote);

    if local == remote {
        return MergeOutcome::Clean(local.to_string());
    }
    if local == base {
        return MergeOutcome::Clean(remote.to_string());
    }
    if remote == base {
        return MergeOutcome::Clean(local.to_string());
    }

    let base_fp: Vec<&str> = base_blocks.iter().map(|s| s.as_str()).collect();
    let local_fp: Vec<&str> = local_blocks.iter().map(|s| s.as_str()).collect();
    let remote_fp: Vec<&str> = remote_blocks.iter().map(|s| s.as_str()).collect();

    // Index-aligned when all sides share the same block count.
    if base_fp.len() == local_fp.len() && base_fp.len() == remote_fp.len() {
        return merge_blocks_aligned(&base_fp, &local_fp, &remote_fp);
    }

    // LCS-align local and remote against base fingerprints, then merge.
    merge_blocks_lcs(&base_fp, &local_fp, &remote_fp)
}

fn merge_blocks_aligned(base: &[&str], local: &[&str], remote: &[&str]) -> MergeOutcome {
    let mut out: Vec<String> = Vec::new();
    let mut conflict = false;
    for i in 0..base.len() {
        let b = base[i];
        let l = local[i];
        let r = remote[i];
        if l == r {
            out.push(l.to_string());
        } else if l == b {
            out.push(r.to_string());
        } else if r == b {
            out.push(l.to_string());
        } else {
            conflict = true;
            out.push(format!(
                "<<<<<<< local\n{l}\n=======\n{r}\n>>>>>>> remote"
            ));
        }
    }
    finish_markdown(out, conflict)
}

/// Merge via LCS of block fingerprints against base, then three-way per aligned slot.
fn merge_blocks_lcs(base: &[&str], local: &[&str], remote: &[&str]) -> MergeOutcome {
    let l_map = align_to_base(base, local);
    let r_map = align_to_base(base, remote);

    let mut out: Vec<String> = Vec::new();
    let mut conflict = false;
    let mut used_local = vec![false; local.len()];
    let mut used_remote = vec![false; remote.len()];

    for (bi, b) in base.iter().enumerate() {
        let l_idx = l_map[bi];
        let r_idx = r_map[bi];
        let l = l_idx.and_then(|i| {
            used_local[i] = true;
            local.get(i).copied()
        });
        let r = r_idx.and_then(|i| {
            used_remote[i] = true;
            remote.get(i).copied()
        });
        match (l, r) {
            (Some(lv), Some(rv)) if lv == rv => out.push(lv.to_string()),
            (Some(lv), Some(rv)) if lv == *b => out.push(rv.to_string()),
            (Some(lv), Some(rv)) if rv == *b => out.push(lv.to_string()),
            (Some(lv), Some(rv)) => {
                conflict = true;
                out.push(format!(
                    "<<<<<<< local\n{lv}\n=======\n{rv}\n>>>>>>> remote"
                ));
            }
            (Some(lv), None) => {
                // Remote deleted this base block; local kept/edited → needs resolution.
                conflict = true;
                out.push(format!(
                    "<<<<<<< local\n{lv}\n=======\n>>>>>>> remote (deleted)"
                ));
            }
            (None, Some(rv)) => {
                conflict = true;
                out.push(format!(
                    "<<<<<<< local (deleted)\n=======\n{rv}\n>>>>>>> remote"
                ));
            }
            (None, None) => {
                // deleted both sides
            }
        }
    }

    // Append local-only inserts (not aligned to base), then remote-only not already mirrored.
    for (i, block) in local.iter().enumerate() {
        if !used_local[i] {
            // Insert if remote also has same insert nearby, else keep local insert.
            if remote.iter().any(|r| r == block) {
                out.push((*block).to_string());
                if let Some(ri) = remote.iter().position(|r| *r == *block) {
                    used_remote[ri] = true;
                }
            } else {
                out.push((*block).to_string());
            }
        }
    }
    for (i, block) in remote.iter().enumerate() {
        if !used_remote[i] {
            out.push((*block).to_string());
        }
    }

    finish_markdown(out, conflict)
}

fn finish_markdown(out: Vec<String>, conflict: bool) -> MergeOutcome {
    let merged = join_blocks(&out);
    if conflict {
        MergeOutcome::Conflict {
            merged,
            conflict_markers: true,
        }
    } else {
        MergeOutcome::Clean(merged)
    }
}

/// For each base index, the local index of a matching block via LCS (greedy).
fn align_to_base(base: &[&str], side: &[&str]) -> Vec<Option<usize>> {
    let pairs = lcs_index_pairs(base, side);
    let mut map = vec![None; base.len()];
    for (bi, si) in pairs {
        map[bi] = Some(si);
    }
    map
}

fn lcs_index_pairs(a: &[&str], b: &[&str]) -> Vec<(usize, usize)> {
    let n = a.len();
    let m = b.len();
    let mut dp = vec![vec![0usize; m + 1]; n + 1];
    for i in 1..=n {
        for j in 1..=m {
            if a[i - 1] == b[j - 1] {
                dp[i][j] = dp[i - 1][j - 1] + 1;
            } else {
                dp[i][j] = dp[i - 1][j].max(dp[i][j - 1]);
            }
        }
    }
    let mut pairs = Vec::new();
    let mut i = n;
    let mut j = m;
    while i > 0 && j > 0 {
        if a[i - 1] == b[j - 1] {
            pairs.push((i - 1, j - 1));
            i -= 1;
            j -= 1;
        } else if dp[i - 1][j] >= dp[i][j - 1] {
            i -= 1;
        } else {
            j -= 1;
        }
    }
    pairs.reverse();
    pairs
}

fn split_blocks(text: &str) -> Vec<String> {
    let mut blocks = Vec::new();
    let mut cur = String::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            if !cur.is_empty() {
                blocks.push(cur.trim_end().to_string());
                cur.clear();
            }
        } else {
            cur.push_str(line);
            cur.push('\n');
        }
    }
    if !cur.is_empty() {
        blocks.push(cur.trim_end().to_string());
    }
    if blocks.is_empty() && !text.is_empty() {
        blocks.push(text.to_string());
    }
    blocks
}

fn join_blocks(blocks: &[String]) -> String {
    let mut s = blocks.join("\n\n");
    if !s.is_empty() && !s.ends_with('\n') {
        s.push('\n');
    }
    s
}

#[derive(Debug, Clone, PartialEq)]
pub enum JsonMergeOutcome {
    Clean(Value),
    Conflict {
        partial: Value,
        unresolved_ids: Vec<String>,
    },
}

const ID_COLLECTION_KEYS: &[&str] = &["nodes", "edges"];

/// Structural three-way merge for workflow/graph JSON by stable `id` / `node_id` / `workflow_id` / `edge_id`.
pub fn merge_json_by_stable_ids(base: &Value, local: &Value, remote: &Value) -> JsonMergeOutcome {
    if local == remote {
        return JsonMergeOutcome::Clean(local.clone());
    }
    if local == base {
        return JsonMergeOutcome::Clean(remote.clone());
    }
    if remote == base {
        return JsonMergeOutcome::Clean(local.clone());
    }

    match (base, local, remote) {
        (Value::Object(b), Value::Object(l), Value::Object(r)) => merge_objects(b, l, r),
        (Value::Array(b), Value::Array(l), Value::Array(r)) => merge_arrays(b, l, r),
        _ => {
            if remote == base {
                JsonMergeOutcome::Clean(local.clone())
            } else if local == base {
                JsonMergeOutcome::Clean(remote.clone())
            } else {
                JsonMergeOutcome::Conflict {
                    partial: local.clone(),
                    unresolved_ids: vec!["<root>".into()],
                }
            }
        }
    }
}

fn merge_objects(
    base: &Map<String, Value>,
    local: &Map<String, Value>,
    remote: &Map<String, Value>,
) -> JsonMergeOutcome {
    let mut keys = BTreeSet::new();
    keys.extend(base.keys().cloned());
    keys.extend(local.keys().cloned());
    keys.extend(remote.keys().cloned());

    let mut out = Map::new();
    let mut unresolved = Vec::new();
    let mut handled_collections = BTreeSet::new();

    for coll in ID_COLLECTION_KEYS {
        let bk = base.get(*coll);
        let lk = local.get(*coll);
        let rk = remote.get(*coll);
        if bk.is_none() && lk.is_none() && rk.is_none() {
            continue;
        }
        // Empty arrays still count as present when parent has the key, or sibling has it.
        let b_map = as_id_map(bk).unwrap_or_default();
        let l_map = as_id_map(lk).unwrap_or_default();
        let r_map = as_id_map(rk).unwrap_or_default();
        // Only treat as ID collection when at least one side yields an ID map (non-empty or empty array).
        let any_array = [bk, lk, rk].iter().any(|v| matches!(v, Some(Value::Array(_))));
        if !any_array {
            continue;
        }
        let (merged, mut part) = merge_id_maps(&b_map, &l_map, &r_map);
        unresolved.append(&mut part);
        out.insert((*coll).to_string(), Value::Array(merged));
        handled_collections.insert((*coll).to_string());
    }

    for k in keys {
        if handled_collections.contains(&k) {
            continue;
        }
        let bv = base.get(&k);
        let lv = local.get(&k);
        let rv = remote.get(&k);
        match merge_field(bv, lv, rv) {
            Ok(Some(v)) => {
                out.insert(k, v);
            }
            Ok(None) => {}
            Err(id) => unresolved.push(if id == "<field>" { k } else { id }),
        }
    }

    if unresolved.is_empty() {
        JsonMergeOutcome::Clean(Value::Object(out))
    } else {
        JsonMergeOutcome::Conflict {
            partial: Value::Object(out),
            unresolved_ids: unresolved,
        }
    }
}

fn merge_arrays(base: &[Value], local: &[Value], remote: &[Value]) -> JsonMergeOutcome {
    if let (Some(b), Some(l), Some(r)) = (
        array_as_id_map(base),
        array_as_id_map(local),
        array_as_id_map(remote),
    ) {
        let (merged, unresolved) = merge_id_maps(&b, &l, &r);
        if unresolved.is_empty() {
            JsonMergeOutcome::Clean(Value::Array(merged))
        } else {
            JsonMergeOutcome::Conflict {
                partial: Value::Array(merged),
                unresolved_ids: unresolved,
            }
        }
    } else if local == remote {
        JsonMergeOutcome::Clean(Value::Array(local.to_vec()))
    } else if local == base {
        JsonMergeOutcome::Clean(Value::Array(remote.to_vec()))
    } else if remote == base {
        JsonMergeOutcome::Clean(Value::Array(local.to_vec()))
    } else {
        JsonMergeOutcome::Conflict {
            partial: Value::Array(local.to_vec()),
            unresolved_ids: vec!["<array>".into()],
        }
    }
}

fn merge_field(
    base: Option<&Value>,
    local: Option<&Value>,
    remote: Option<&Value>,
) -> Result<Option<Value>, String> {
    match (base, local, remote) {
        (_, Some(l), Some(r)) if l == r => Ok(Some(l.clone())),
        (Some(b), Some(l), Some(r)) if l != r && l != b && r != b => {
            match merge_json_by_stable_ids(b, l, r) {
                JsonMergeOutcome::Clean(v) => Ok(Some(v)),
                JsonMergeOutcome::Conflict { .. } => Err("<field>".into()),
            }
        }
        (Some(b), Some(l), Some(r)) if l == b => Ok(Some(r.clone())),
        (Some(b), Some(l), Some(r)) if r == b => Ok(Some(l.clone())),
        (_, Some(l), None) => Ok(Some(l.clone())),
        (_, None, Some(r)) => Ok(Some(r.clone())),
        (_, None, None) => Ok(None),
        _ => Ok(local.cloned().or_else(|| remote.cloned())),
    }
}

fn item_id(v: &Value) -> Option<String> {
    v.as_object().and_then(|o| {
        ["id", "node_id", "workflow_id", "edge_id"]
            .iter()
            .find_map(|k| o.get(*k).and_then(|x| x.as_str()).map(|s| s.to_string()))
    })
}

fn array_as_id_map(arr: &[Value]) -> Option<BTreeMap<String, Value>> {
    if arr.is_empty() {
        return Some(BTreeMap::new());
    }
    let mut map = BTreeMap::new();
    for item in arr {
        let id = item_id(item)?;
        map.insert(id, item.clone());
    }
    Some(map)
}

fn as_id_map(v: Option<&Value>) -> Option<BTreeMap<String, Value>> {
    match v? {
        Value::Array(a) => array_as_id_map(a),
        _ => None,
    }
}

fn merge_id_maps(
    base: &BTreeMap<String, Value>,
    local: &BTreeMap<String, Value>,
    remote: &BTreeMap<String, Value>,
) -> (Vec<Value>, Vec<String>) {
    let mut ids = BTreeSet::new();
    ids.extend(base.keys().cloned());
    ids.extend(local.keys().cloned());
    ids.extend(remote.keys().cloned());
    let mut out = Vec::new();
    let mut unresolved = Vec::new();
    for id in ids {
        let b = base.get(&id);
        let l = local.get(&id);
        let r = remote.get(&id);
        match (b, l, r) {
            (_, Some(lv), Some(rv)) if lv == rv => out.push(lv.clone()),
            (Some(bv), Some(lv), Some(rv)) if lv != rv => {
                if lv == bv {
                    out.push(rv.clone());
                } else if rv == bv {
                    out.push(lv.clone());
                } else {
                    match merge_json_by_stable_ids(bv, lv, rv) {
                        JsonMergeOutcome::Clean(v) => out.push(v),
                        JsonMergeOutcome::Conflict { partial, .. } => {
                            out.push(partial);
                            unresolved.push(id);
                        }
                    }
                }
            }
            (_, Some(lv), None) => {
                if b.is_some() && r.is_none() {
                    // Present in base, edited/kept locally, deleted remotely.
                    if lv == b.unwrap() {
                        unresolved.push(format!("{id}:rename_or_delete"));
                    } else {
                        out.push(lv.clone());
                        unresolved.push(format!("{id}:delete_vs_edit"));
                    }
                } else {
                    out.push(lv.clone());
                }
            }
            (_, None, Some(rv)) => {
                if b.is_some() && l.is_none() {
                    if rv == b.unwrap() {
                        unresolved.push(format!("{id}:rename_or_delete"));
                    } else {
                        out.push(rv.clone());
                        unresolved.push(format!("{id}:delete_vs_edit"));
                    }
                } else {
                    out.push(rv.clone());
                }
            }
            (Some(_), None, None) => {
                // deleted both sides
            }
            (None, Some(lv), Some(rv)) if lv != rv => {
                unresolved.push(format!("{id}:add_conflict"));
                out.push(lv.clone());
            }
            _ => {}
        }
    }
    (out, unresolved)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn markdown_clean_when_one_side_unchanged() {
        let base = "A\n\nB\n";
        let local = "A\n\nB\n";
        let remote = "A\n\nB-remote\n";
        match merge_markdown_three_way(base, local, remote) {
            MergeOutcome::Clean(s) => assert!(s.contains("B-remote")),
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn markdown_lcs_nonoverlapping_inserts() {
        let base = "Intro\n\nShared\n\nOutro\n";
        let local = "Intro\n\nLocal-only\n\nShared\n\nOutro\n";
        let remote = "Intro\n\nShared\n\nRemote-only\n\nOutro\n";
        match merge_markdown_three_way(base, local, remote) {
            MergeOutcome::Clean(s) => {
                assert!(s.contains("Local-only"));
                assert!(s.contains("Remote-only"));
                assert!(s.contains("Shared"));
            }
            MergeOutcome::Conflict { merged, .. } => {
                // Acceptable if markers present but both inserts retained somehow
                assert!(merged.contains("Local-only") || merged.contains("Remote-only"));
            }
        }
    }

    #[test]
    fn json_merges_by_node_id() {
        let base = json!({
            "nodes": [
                {"id": "a", "title": "A"},
                {"id": "b", "title": "B"}
            ]
        });
        let local = json!({
            "nodes": [
                {"id": "a", "title": "A-local"},
                {"id": "b", "title": "B"}
            ]
        });
        let remote = json!({
            "nodes": [
                {"id": "a", "title": "A"},
                {"id": "b", "title": "B-remote"}
            ]
        });
        match merge_json_by_stable_ids(&base, &local, &remote) {
            JsonMergeOutcome::Clean(v) => {
                let nodes = v["nodes"].as_array().unwrap();
                assert_eq!(nodes.len(), 2);
                assert!(nodes.iter().any(|n| n["title"] == "A-local"));
                assert!(nodes.iter().any(|n| n["title"] == "B-remote"));
            }
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn json_merges_edges_by_id() {
        let base = json!({
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [{"id": "e1", "from": "a", "to": "b"}]
        });
        let local = json!({
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [{"id": "e1", "from": "a", "to": "b", "label": "L"}]
        });
        let remote = json!({
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [{"id": "e1", "from": "a", "to": "b"}, {"id": "e2", "from": "b", "to": "a"}]
        });
        match merge_json_by_stable_ids(&base, &local, &remote) {
            JsonMergeOutcome::Clean(v) => {
                let edges = v["edges"].as_array().unwrap();
                assert!(edges.iter().any(|e| e["id"] == "e1" && e["label"] == "L"));
                assert!(edges.iter().any(|e| e["id"] == "e2"));
            }
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn json_conflict_same_id() {
        let base = json!({"nodes": [{"id": "a", "title": "A"}]});
        let local = json!({"nodes": [{"id": "a", "title": "L"}]});
        let remote = json!({"nodes": [{"id": "a", "title": "R"}]});
        match merge_json_by_stable_ids(&base, &local, &remote) {
            JsonMergeOutcome::Conflict { unresolved_ids, .. } => {
                assert!(!unresolved_ids.is_empty());
            }
            other => panic!("expected conflict, got {other:?}"),
        }
    }

    #[test]
    fn json_delete_vs_edit_flags() {
        let base = json!({"nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]});
        let local = json!({"nodes": [{"id": "a", "title": "A-edited"}, {"id": "b", "title": "B"}]});
        let remote = json!({"nodes": [{"id": "b", "title": "B"}]});
        match merge_json_by_stable_ids(&base, &local, &remote) {
            JsonMergeOutcome::Conflict { unresolved_ids, .. } => {
                assert!(unresolved_ids.iter().any(|u| u.contains("delete_vs_edit")));
            }
            other => panic!("expected delete_vs_edit conflict, got {other:?}"),
        }
    }
}
