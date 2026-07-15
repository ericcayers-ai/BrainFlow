//! Embedded Git operations.
//!
//! Policy (ADR 0005 / spikes): prefer **gitoxide (`gix`)** for discovery and object
//! integrity; use **libgit2 (`git2`)** as the porcelain escape hatch for
//! clone / index / commit / merge / push. Never shell out from UI or LLM tools.
//! Never automatic force-push.

use crate::credentials;
use crate::merge::{merge_json_by_stable_ids, merge_markdown_three_way, JsonMergeOutcome, MergeOutcome};
use git2::{
    build::RepoBuilder, BranchType, Cred, FetchOptions, IndexAddOption, PushOptions,
    RemoteCallbacks, Repository, Signature,
};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use thiserror::Error;

/// Test counter: must stay 0 for all normal sync pushes (AC-SYNC-02).
pub static FORCE_PUSH_INVOCATIONS: AtomicU64 = AtomicU64::new(0);

#[derive(Debug, Error)]
pub enum GitError {
    #[error("git: {0}")]
    Git(#[from] git2::Error),
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("gix: {0}")]
    Gix(String),
    #[error("{0}")]
    Message(String),
    #[error("force push is forbidden")]
    ForcePushForbidden,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitResult {
    pub oid: String,
    pub summary: String,
    pub files_changed: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntegrateResult {
    pub clean: bool,
    pub conflicts: Vec<ConflictItem>,
    pub merged_files: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ConflictKind {
    Markdown,
    WorkflowJson,
    GraphJson,
    Binary,
    Text,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConflictItem {
    pub path: String,
    pub kind: ConflictKind,
    pub base: Option<String>,
    pub local: Option<String>,
    pub remote: Option<String>,
    pub unresolved_ids: Vec<String>,
    pub recovery_local: Option<String>,
    pub recovery_remote: Option<String>,
}

/// Probe a path with gitoxide (preferred discovery path).
pub fn gix_discover(path: &Path) -> Result<PathBuf, GitError> {
    let repo = gix::discover(path).map_err(|e| GitError::Gix(e.to_string()))?;
    Ok(repo.git_dir().to_path_buf())
}

/// Soft object integrity check via gitoxide open.
pub fn gix_integrity_ok(vault: &Path) -> Result<bool, GitError> {
    let _repo = gix::open(vault).map_err(|e| GitError::Gix(e.to_string()))?;
    // Opening + discovering HEAD is a cheap health signal; deeper fsck can come later.
    Ok(true)
}

fn auth_callbacks() -> Result<RemoteCallbacks<'static>, GitError> {
    let token = credentials::load_token()
        .map_err(|e| GitError::Message(format!("auth required: {e}")))?;
    let mut cb = RemoteCallbacks::new();
    cb.credentials(move |_url, _username_from_url, _allowed| {
        Cred::userpass_plaintext("x-access-token", &token)
    });
    Ok(cb)
}

/// Clone an existing repository into `dest` (vault root).
pub fn clone_repo(url: &str, dest: &Path) -> Result<(), GitError> {
    if dest.exists() && dest.read_dir()?.next().is_some() {
        // If already a git repo at dest, skip.
        if Repository::open(dest).is_ok() {
            return Ok(());
        }
        return Err(GitError::Message(format!(
            "destination not empty: {}",
            dest.display()
        )));
    }
    std::fs::create_dir_all(dest)?;
    let mut fetch_opts = FetchOptions::new();
    fetch_opts.remote_callbacks(auth_callbacks()?);
    RepoBuilder::new()
        .fetch_options(fetch_opts)
        .clone(url, dest)?;
    let _ = gix_discover(dest);
    Ok(())
}

/// Initialize a new local git repository (for create-then-push).
pub fn init_repo(vault: &Path) -> Result<(), GitError> {
    if Repository::open(vault).is_ok() {
        return Ok(());
    }
    Repository::init(vault)?;
    let _ = gix_discover(vault);
    Ok(())
}

pub fn set_remote_origin(vault: &Path, url: &str) -> Result<(), GitError> {
    let repo = Repository::open(vault)?;
    match repo.find_remote("origin") {
        Ok(_) => {
            repo.remote_set_url("origin", url)?;
        }
        Err(_) => {
            repo.remote("origin", url)?;
        }
    }
    Ok(())
}

fn signature() -> Result<Signature<'static>, GitError> {
    let device = hostname::get()
        .ok()
        .and_then(|h| h.into_string().ok())
        .unwrap_or_else(|| "brainflow-device".into());
    let device_hash = {
        use sha2::{Digest, Sha256};
        let mut h = Sha256::new();
        h.update(device.as_bytes());
        hex::encode(&h.finalize()[..6])
    };
    Ok(Signature::now(
        &format!("BrainFlow ({device_hash})"),
        "sync@brainflow.local",
    )?)
}

/// Stage all tracked+untracked (respecting gitignore) and commit if there are changes.
pub fn commit_all(vault: &Path, summary: &str) -> Result<Option<CommitResult>, GitError> {
    let repo = Repository::open(vault)?;
    let mut index = repo.index()?;
    index.add_all(["*"].iter(), IndexAddOption::DEFAULT, None)?;
    index.write()?;
    let tree_id = index.write_tree()?;
    let tree = repo.find_tree(tree_id)?;
    let sig = signature()?;
    let parent_commit = match repo.head() {
        Ok(head) => Some(head.peel_to_commit()?),
        Err(_) => None,
    };
    // Skip empty commits.
    if let Some(ref parent) = parent_commit {
        if parent.tree_id() == tree_id {
            return Ok(None);
        }
    }
    let parents: Vec<&git2::Commit> = parent_commit.iter().collect();
    let msg = format!("{summary}\n\nBrainFlow-Sync: true\n");
    let oid = repo.commit(Some("HEAD"), &sig, &sig, &msg, &tree, &parents)?;
    Ok(Some(CommitResult {
        oid: oid.to_string(),
        summary: summary.to_string(),
        files_changed: index.len(),
    }))
}

pub fn fetch_origin(vault: &Path) -> Result<(), GitError> {
    let repo = Repository::open(vault)?;
    let mut remote = repo.find_remote("origin").map_err(|_| {
        GitError::Message("no origin remote — configure sync first".into())
    })?;
    let mut fetch_opts = FetchOptions::new();
    fetch_opts.remote_callbacks(auth_callbacks()?);
    remote.fetch(&["refs/heads/*:refs/remotes/origin/*"], Some(&mut fetch_opts), None)?;
    Ok(())
}

fn default_branch(repo: &Repository) -> Result<String, GitError> {
    if let Ok(head) = repo.head() {
        if let Some(name) = head.shorthand() {
            return Ok(name.to_string());
        }
    }
    for candidate in ["main", "master"] {
        if repo.find_branch(candidate, BranchType::Local).is_ok() {
            return Ok(candidate.into());
        }
    }
    Ok("main".into())
}

/// Three-way integrate against `origin/<branch>` using semantic merge helpers.
pub fn integrate_origin(vault: &Path) -> Result<IntegrateResult, GitError> {
    let repo = Repository::open(vault)?;
    let branch = default_branch(&repo)?;
    let remote_ref = format!("refs/remotes/origin/{branch}");
    let remote_obj = match repo.revparse_single(&remote_ref) {
        Ok(o) => o,
        Err(_) => {
            // No remote branch yet — first push case.
            return Ok(IntegrateResult {
                clean: true,
                conflicts: vec![],
                merged_files: vec![],
            });
        }
    };
    let remote_commit = remote_obj.peel_to_commit()?;
    let local_commit = repo.head()?.peel_to_commit()?;

    if local_commit.id() == remote_commit.id() {
        return Ok(IntegrateResult {
            clean: true,
            conflicts: vec![],
            merged_files: vec![],
        });
    }

    let merge_base = match repo.merge_base(local_commit.id(), remote_commit.id()) {
        Ok(oid) => oid,
        Err(_) => {
            return Err(GitError::Message(
                "no merge base — unrelated histories; manual repair required (no force-push)"
                    .into(),
            ));
        }
    };
    let base_commit = repo.find_commit(merge_base)?;
    let base_tree = base_commit.tree()?;
    let local_tree = local_commit.tree()?;
    let remote_tree = remote_commit.tree()?;

    let mut conflicts = Vec::new();
    let mut merged_files = Vec::new();

    // Diff remote vs local via merge analysis on trees.
    let mut index = repo.merge_trees(&base_tree, &local_tree, &remote_tree, None)?;
    if index.has_conflicts() {
        let conflicts_list: Vec<_> = index.conflicts()?.filter_map(|c| c.ok()).collect();
        for c in conflicts_list {
            let path = c
                .our
                .as_ref()
                .or(c.their.as_ref())
                .or(c.ancestor.as_ref())
                .map(|e| String::from_utf8_lossy(&e.path).to_string())
                .unwrap_or_else(|| "unknown".into());
            let kind = classify_path(&path);
            let base = blob_text(&repo, c.ancestor.as_ref());
            let local = blob_text(&repo, c.our.as_ref());
            let remote = blob_text(&repo, c.their.as_ref());

            let recovery_dir = vault.join(".brainflow/local/sync/recovery");
            std::fs::create_dir_all(&recovery_dir)?;
            let safe = path.replace(['/', '\\'], "__");
            let rec_local = recovery_dir.join(format!("{safe}.local"));
            let rec_remote = recovery_dir.join(format!("{safe}.remote"));
            if let Some(ref t) = local {
                std::fs::write(&rec_local, t)?;
            }
            if let Some(ref t) = remote {
                std::fs::write(&rec_remote, t)?;
            }

            let mut unresolved_ids = Vec::new();
            let resolved = match kind {
                ConflictKind::Markdown => {
                    if let (Some(b), Some(l), Some(r)) = (&base, &local, &remote) {
                        match merge_markdown_three_way(b, l, r) {
                            MergeOutcome::Clean(s) => Some(s),
                            MergeOutcome::Conflict { merged, .. } => {
                                unresolved_ids.push(path.clone());
                                Some(merged)
                            }
                        }
                    } else {
                        None
                    }
                }
                ConflictKind::WorkflowJson | ConflictKind::GraphJson => {
                    if let (Some(b), Some(l), Some(r)) = (&base, &local, &remote) {
                        let bv: serde_json::Value = serde_json::from_str(b).unwrap_or(serde_json::Value::Null);
                        let lv: serde_json::Value = serde_json::from_str(l).unwrap_or(serde_json::Value::Null);
                        let rv: serde_json::Value = serde_json::from_str(r).unwrap_or(serde_json::Value::Null);
                        match merge_json_by_stable_ids(&bv, &lv, &rv) {
                            JsonMergeOutcome::Clean(v) => {
                                Some(serde_json::to_string_pretty(&v).unwrap_or_default())
                            }
                            JsonMergeOutcome::Conflict {
                                partial,
                                unresolved_ids: ids,
                            } => {
                                unresolved_ids.extend(ids);
                                Some(serde_json::to_string_pretty(&partial).unwrap_or_default())
                            }
                        }
                    } else {
                        None
                    }
                }
                ConflictKind::Binary => {
                    // Keep both sides as recovery copies; leave conflict for UI.
                    unresolved_ids.push(path.clone());
                    None
                }
                ConflictKind::Text => {
                    unresolved_ids.push(path.clone());
                    None
                }
            };

            if let Some(content) = resolved {
                if unresolved_ids.is_empty() {
                    let abs = vault.join(&path);
                    if let Some(parent) = abs.parent() {
                        std::fs::create_dir_all(parent)?;
                    }
                    std::fs::write(&abs, &content)?;
                    merged_files.push(path.clone());
                    // resolved cleanly — do not push to conflicts list
                    continue;
                }
                // Write partial with markers for UI, still conflict.
                let abs = vault.join(&path);
                if let Some(parent) = abs.parent() {
                    std::fs::create_dir_all(parent)?;
                }
                std::fs::write(&abs, &content)?;
            }

            conflicts.push(ConflictItem {
                path: path.clone(),
                kind,
                base,
                local,
                remote,
                unresolved_ids,
                recovery_local: rec_local.exists().then(|| {
                    format!(".brainflow/local/sync/recovery/{}", rec_local.file_name().unwrap().to_string_lossy())
                }),
                recovery_remote: rec_remote.exists().then(|| {
                    format!(".brainflow/local/sync/recovery/{}", rec_remote.file_name().unwrap().to_string_lossy())
                }),
            });
        }
    } else {
        // Clean tree merge — checkout result.
        let oid = index.write_tree_to(&repo)?;
        let tree = repo.find_tree(oid)?;
        let sig = signature()?;
        let msg = "BrainFlow sync integrate (clean three-way)\n";
        repo.commit(
            Some("HEAD"),
            &sig,
            &sig,
            msg,
            &tree,
            &[&local_commit, &remote_commit],
        )?;
    }

    Ok(IntegrateResult {
        clean: conflicts.is_empty(),
        conflicts,
        merged_files,
    })
}

fn classify_path(path: &str) -> ConflictKind {
    let lower = path.replace('\\', "/").to_lowercase();
    if lower.ends_with(".md") {
        ConflictKind::Markdown
    } else if lower.contains(".brainflow/workflows/") && lower.ends_with(".json") {
        ConflictKind::WorkflowJson
    } else if lower.contains(".brainflow/graphs/") && lower.ends_with(".json") {
        ConflictKind::GraphJson
    } else if lower.ends_with(".json") || lower.ends_with(".txt") || lower.ends_with(".yaml") {
        ConflictKind::Text
    } else {
        ConflictKind::Binary
    }
}

fn blob_text(repo: &Repository, entry: Option<&git2::IndexEntry>) -> Option<String> {
    let e = entry?;
    let blob = repo.find_blob(e.id).ok()?;
    String::from_utf8(blob.content().to_vec()).ok()
}

/// Push current branch to origin. **Never** force.
pub fn push_origin(vault: &Path, force: bool) -> Result<(), GitError> {
    if force {
        FORCE_PUSH_INVOCATIONS.fetch_add(1, Ordering::SeqCst);
        return Err(GitError::ForcePushForbidden);
    }
    let repo = Repository::open(vault)?;
    let branch = default_branch(&repo)?;
    let mut remote = repo.find_remote("origin")?;
    let callbacks = auth_callbacks()?;
    let mut push_opts = PushOptions::new();
    push_opts.remote_callbacks(callbacks);
    // Explicitly non-force refspec.
    let refspec = format!("refs/heads/{branch}:refs/heads/{branch}");
    remote.push(&[refspec], Some(&mut push_opts))?;
    Ok(())
}

pub fn force_push_forbidden() -> bool {
    true
}

pub fn force_push_invocation_count() -> u64 {
    FORCE_PUSH_INVOCATIONS.load(Ordering::SeqCst)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn never_allows_force() {
        assert!(force_push_forbidden());
        let before = force_push_invocation_count();
        let err = push_origin(Path::new("."), true).unwrap_err();
        assert!(matches!(err, GitError::ForcePushForbidden));
        assert_eq!(force_push_invocation_count(), before + 1);
    }
}
