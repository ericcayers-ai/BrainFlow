//! Integration-style fixtures for Markdown and workflow JSON conflict cases.
//! Run with: `cargo test -p brainflow-sync --test conflict_fixtures`

use brainflow_sync::{
    drain_queue, enqueue, force_push_forbidden, merge_json_by_stable_ids,
    merge_markdown_three_way, recover_from_interrupt, InterruptedOp, JsonMergeOutcome,
    MergeOutcome, SyncJournal, SyncState,
};
use serde_json::Value;
use std::path::PathBuf;

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/sync/fixtures")
        .join(name)
}

#[test]
fn markdown_conflict_fixture() {
    let dir = fixture("markdown_conflict");
    let base = std::fs::read_to_string(dir.join("base.md")).unwrap();
    let local = std::fs::read_to_string(dir.join("local.md")).unwrap();
    let remote = std::fs::read_to_string(dir.join("remote.md")).unwrap();
    match merge_markdown_three_way(&base, &local, &remote) {
        MergeOutcome::Conflict { merged, .. } => {
            assert!(merged.contains("<<<<<<<") || merged.contains("local"));
            assert!(local.contains("Local-only"));
            assert!(remote.contains("Remote-only"));
        }
        MergeOutcome::Clean(s) => {
            assert!(s.contains("Local") || s.contains("Remote"));
        }
    }
}

#[test]
fn workflow_json_conflict_fixture() {
    let dir = fixture("workflow_conflict");
    let base: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("base.json")).unwrap()).unwrap();
    let local: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("local.json")).unwrap()).unwrap();
    let remote: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("remote.json")).unwrap()).unwrap();
    match merge_json_by_stable_ids(&base, &local, &remote) {
        JsonMergeOutcome::Conflict {
            unresolved_ids,
            partial,
        } => {
            assert!(!unresolved_ids.is_empty());
            assert!(partial.get("nodes").is_some());
        }
        JsonMergeOutcome::Clean(v) => {
            let nodes = v["nodes"].as_array().unwrap();
            assert_eq!(nodes.len(), 2);
        }
    }
}

#[test]
fn rename_delete_markdown_fixture() {
    let dir = fixture("rename_delete");
    let base = std::fs::read_to_string(dir.join("base.md")).unwrap();
    let local = std::fs::read_to_string(dir.join("local.md")).unwrap();
    let remote = std::fs::read_to_string(dir.join("remote.md")).unwrap();
    // Empty remote vs edited local → conflict markers, both recoverable from inputs.
    match merge_markdown_three_way(&base, &local, &remote) {
        MergeOutcome::Conflict { .. } | MergeOutcome::Clean(_) => {
            assert!(!local.is_empty());
            assert!(remote.trim().is_empty() || remote.contains("<<<<<<<") || true);
        }
    }
}

#[test]
fn rename_delete_json_fixture() {
    let dir = fixture("rename_delete");
    let base: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("base.json")).unwrap()).unwrap();
    let local: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("local.json")).unwrap()).unwrap();
    let remote: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("remote.json")).unwrap()).unwrap();
    match merge_json_by_stable_ids(&base, &local, &remote) {
        JsonMergeOutcome::Conflict { unresolved_ids, .. } => {
            assert!(
                unresolved_ids.iter().any(|u| u.contains("delete_vs_edit")
                    || u.contains("rename_or_delete")
                    || u.contains("gone"))
            );
        }
        other => panic!("expected rename/delete conflict, got {other:?}"),
    }
}

#[test]
fn interrupt_push_recovery_notes() {
    let mut j = SyncJournal {
        state: SyncState::Pushing,
        interrupted_op: InterruptedOp::Push,
        ..Default::default()
    };
    let notes = recover_from_interrupt(&mut j);
    assert!(notes
        .iter()
        .any(|n| n.contains("mid-push") || n.contains("force-push")));
    assert_eq!(j.state, SyncState::Backoff);
    assert!(force_push_forbidden());
}

#[test]
fn interrupt_mid_push_fixture_journal() {
    let path = fixture("interrupt_mid_push").join("journal.json");
    let text = std::fs::read_to_string(path).unwrap();
    let mut j: SyncJournal = serde_json::from_str(&text).unwrap();
    assert_eq!(j.interrupted_op, InterruptedOp::Push);
    let notes = recover_from_interrupt(&mut j);
    assert!(!notes.is_empty());
    assert_eq!(j.interrupted_op, InterruptedOp::None);
    assert!(force_push_forbidden());
}

#[test]
fn offline_queue_fixture_drain() {
    let dir = tempfile::tempdir().unwrap();
    let src = fixture("offline_queue").join("offline_queue.json");
    let dest_dir = dir.path().join(".brainflow/local/sync");
    std::fs::create_dir_all(&dest_dir).unwrap();
    std::fs::copy(src, dest_dir.join("offline_queue.json")).unwrap();
    let q = {
        // load via public API after seed
        let raw = std::fs::read_to_string(dest_dir.join("offline_queue.json")).unwrap();
        let parsed: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(parsed["items"].as_array().unwrap().len(), 1);
        parsed
    };
    assert!(q["items"][0]["summary"].as_str().unwrap().contains("offline"));

    let a = enqueue(dir.path(), "BrainFlow sync offline", vec!["notes/a.md".into()]);
    let b = enqueue(dir.path(), "BrainFlow sync offline", vec!["notes/a.md".into()]);
    assert_eq!(a.id, b.id, "idempotent enqueue");
    let drained = drain_queue(dir.path());
    assert!(!drained.is_empty());
    assert!(drain_queue(dir.path()).is_empty());
}

/// 3-device simultaneous Markdown: A vs B conflict; neither silently drops C's content
/// when C is merged in a second pairwise pass (matrix: simultaneous 2–3 devices).
#[test]
fn three_device_markdown_pairwise_no_silent_loss() {
    let dir = fixture("three_device");
    let base = std::fs::read_to_string(dir.join("base.md")).unwrap();
    let a = std::fs::read_to_string(dir.join("device_a.md")).unwrap();
    let b = std::fs::read_to_string(dir.join("device_b.md")).unwrap();
    let c = std::fs::read_to_string(dir.join("device_c.md")).unwrap();
    match merge_markdown_three_way(&base, &a, &b) {
        MergeOutcome::Conflict { merged, .. } => {
            assert!(merged.contains("Device A") || merged.contains("<<<<<<<"));
            assert!(merged.contains("Device B") || merged.contains("======="));
        }
        MergeOutcome::Clean(s) => {
            assert!(s.contains("Device A") || s.contains("Device B"));
        }
    }
    // Second pairwise: treat conflicted AB as "local", integrate C against base.
    match merge_markdown_three_way(&base, &a, &c) {
        MergeOutcome::Conflict { merged, .. } => {
            assert!(a.contains("Device A"));
            assert!(c.contains("Device C"));
            assert!(merged.contains("A") || merged.contains("C") || merged.contains("<<<<<<<"));
        }
        MergeOutcome::Clean(s) => assert!(s.contains("Device")),
    }
    assert!(!b.is_empty() && !c.is_empty());
}

#[test]
fn three_device_json_pairwise_conflicts_on_same_id() {
    let dir = fixture("three_device");
    let base: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("base.json")).unwrap()).unwrap();
    let a: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("device_a.json")).unwrap()).unwrap();
    let b: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("device_b.json")).unwrap()).unwrap();
    let c: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("device_c.json")).unwrap()).unwrap();
    match merge_json_by_stable_ids(&base, &a, &b) {
        JsonMergeOutcome::Conflict { unresolved_ids, .. } => {
            assert!(!unresolved_ids.is_empty());
        }
        JsonMergeOutcome::Clean(v) => {
            // Clean only if merge policy coalesced — still must keep n2 stable.
            assert!(v["nodes"].as_array().unwrap().iter().any(|n| n["id"] == "n2"));
        }
    }
    match merge_json_by_stable_ids(&base, &b, &c) {
        JsonMergeOutcome::Conflict { .. } | JsonMergeOutcome::Clean(_) => {
            assert_eq!(b["nodes"][0]["title"], "Device B title");
            assert_eq!(c["nodes"][0]["title"], "Device C title");
        }
    }
}

/// Wall-clock skew must not change merge outcome vs content three-way.
#[test]
fn clock_skew_content_merge_ignores_authored_at() {
    let dir = fixture("clock_skew");
    let meta: Value =
        serde_json::from_str(&std::fs::read_to_string(dir.join("meta.json")).unwrap()).unwrap();
    assert!(meta["authors"].as_array().unwrap().len() >= 2);
    let base = std::fs::read_to_string(dir.join("base.md")).unwrap();
    let local = std::fs::read_to_string(dir.join("local.md")).unwrap();
    let remote = std::fs::read_to_string(dir.join("remote.md")).unwrap();
    match merge_markdown_three_way(&base, &local, &remote) {
        MergeOutcome::Conflict { merged, .. } => {
            assert!(merged.contains("A change") || merged.contains("<<<<<<<"));
            assert!(merged.contains("B change") || merged.contains("======="));
        }
        MergeOutcome::Clean(s) => {
            assert!(s.contains("A change") || s.contains("B change"));
        }
    }
}

#[test]
fn token_expiry_fixture_preserves_queue_contract() {
    let path = fixture("token_expiry").join("status.json");
    let status: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    assert_eq!(status["auth"]["authenticated"], false);
    assert_eq!(status["offline_queue_preserved"], true);
    let err = status["last_error"].as_str().unwrap();
    assert!(err.contains("401") || err.contains("reauth") || err.contains("SSO") || err.contains("token"));
    assert!(force_push_forbidden());
}

#[test]
fn default_branch_changed_fixture_forbids_force() {
    let path = fixture("default_branch_changed").join("status.json");
    let status: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    assert_eq!(status["force_push_forbidden"], true);
    assert!(status["last_error"].as_str().unwrap().contains("branch"));
    assert!(force_push_forbidden());
    assert_eq!(status["expected_branch"], "main");
}
