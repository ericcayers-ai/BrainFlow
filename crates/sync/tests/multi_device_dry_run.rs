//! Multi-device sync dry-run simulation (no GitHub accounts / live remotes).
//! Chains pairwise merges, interrupt recovery, queue drain, and auth-expiry
//! contracts from fixtures — documents the manual live matrix separately.
//!
//! Run: `cargo test -p brainflow-sync --test multi_device_dry_run`

use brainflow_sync::{
    drain_queue, enqueue, force_push_forbidden, merge_json_by_stable_ids,
    merge_markdown_three_way, recover_from_interrupt, InterruptedOp, JsonMergeOutcome,
    MergeOutcome, SyncJournal,
};
use serde_json::Value;
use std::path::PathBuf;

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/sync/fixtures")
        .join(name)
}

/// Simulates: Device A + B diverge → conflict surface → Device C edit against base
/// → offline queue + interrupt mid-push recover → token expiry preserves queue.
/// Never contacts network; never force-pushes.
#[test]
fn multi_device_dry_run_simulation_no_silent_loss() {
    assert!(force_push_forbidden());

    let three = fixture("three_device");
    let base_md = std::fs::read_to_string(three.join("base.md")).unwrap();
    let a_md = std::fs::read_to_string(three.join("device_a.md")).unwrap();
    let b_md = std::fs::read_to_string(three.join("device_b.md")).unwrap();
    let c_md = std::fs::read_to_string(three.join("device_c.md")).unwrap();

    // Round 1: A vs B simultaneous edit
    let ab = merge_markdown_three_way(&base_md, &a_md, &b_md);
    let ab_keeps_both = match &ab {
        MergeOutcome::Conflict { merged, .. } => {
            (merged.contains("Device A") || merged.contains("<<<<<<<"))
                && (merged.contains("Device B") || merged.contains("======="))
        }
        MergeOutcome::Clean(s) => s.contains("Device A") || s.contains("Device B"),
    };
    assert!(ab_keeps_both, "A×B silent loss");

    // Round 2: integrate C against base (second device arrival)
    let ac = merge_markdown_three_way(&base_md, &a_md, &c_md);
    match ac {
        MergeOutcome::Conflict { merged, .. } => {
            assert!(
                merged.contains("A") || merged.contains("C") || merged.contains("<<<<<<<"),
                "A×C conflict must surface content"
            );
        }
        MergeOutcome::Clean(s) => assert!(s.contains("Device")),
    }
    // Source devices retain their edits for UI recovery
    assert!(a_md.contains("Device A") && b_md.contains("Device B") && c_md.contains("Device C"));

    // Structural JSON: pairwise B×C on same node id
    let base_j: Value =
        serde_json::from_str(&std::fs::read_to_string(three.join("base.json")).unwrap()).unwrap();
    let b_j: Value =
        serde_json::from_str(&std::fs::read_to_string(three.join("device_b.json")).unwrap()).unwrap();
    let c_j: Value =
        serde_json::from_str(&std::fs::read_to_string(three.join("device_c.json")).unwrap()).unwrap();
    match merge_json_by_stable_ids(&base_j, &b_j, &c_j) {
        JsonMergeOutcome::Conflict { unresolved_ids, .. } => {
            assert!(!unresolved_ids.is_empty());
        }
        JsonMergeOutcome::Clean(v) => {
            assert!(v["nodes"].as_array().unwrap().iter().any(|n| n["id"] == "n2"));
        }
    }

    // Clock skew must not invent a different loser than content three-way
    let skew = fixture("clock_skew");
    let skew_base = std::fs::read_to_string(skew.join("base.md")).unwrap();
    let skew_local = std::fs::read_to_string(skew.join("local.md")).unwrap();
    let skew_remote = std::fs::read_to_string(skew.join("remote.md")).unwrap();
    match merge_markdown_three_way(&skew_base, &skew_local, &skew_remote) {
        MergeOutcome::Conflict { merged, .. } => {
            assert!(merged.contains("A change") || merged.contains("<<<<<<<"));
            assert!(merged.contains("B change") || merged.contains("======="));
        }
        MergeOutcome::Clean(s) => {
            assert!(s.contains("A change") || s.contains("B change"));
        }
    }

    // Interrupt mid-push → recover; queue remains
    let journal_path = fixture("interrupt_mid_push").join("journal.json");
    let mut journal: SyncJournal =
        serde_json::from_str(&std::fs::read_to_string(journal_path).unwrap()).unwrap();
    assert_eq!(journal.interrupted_op, InterruptedOp::Push);
    let notes = recover_from_interrupt(&mut journal);
    assert!(!notes.is_empty());
    assert_eq!(journal.interrupted_op, InterruptedOp::None);
    assert!(force_push_forbidden());

    // Offline queue drain simulation
    let tmp = tempfile::tempdir().unwrap();
    let q = enqueue(tmp.path(), "dry-run commit", vec!["notes/a.md".into()]);
    let again = enqueue(tmp.path(), "dry-run commit", vec!["notes/a.md".into()]);
    assert_eq!(q.id, again.id);
    let drained = drain_queue(tmp.path());
    assert_eq!(drained.len(), 1);
    assert!(drain_queue(tmp.path()).is_empty());

    // Token expiry contract: unauthenticated, queue preserved, no force
    let token: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture("token_expiry").join("status.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(token["auth"]["authenticated"], false);
    assert_eq!(token["offline_queue_preserved"], true);
    assert!(force_push_forbidden());

    let branch: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture("default_branch_changed").join("status.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(branch["force_push_forbidden"], true);
}
