# Graph suite eval stubs

Projection parity and patch validation stubs. Scale (500 / 5k) and AT testing deferred.

| ID | Intent |
|----|--------|
| `outline_dag_parity` | Same node ids in outline vs DAG projection |
| `patch_dangling_edge` | Invalid patch rejected |
| `diff_versions` | Added node appears in diff |

Run Rust: `cargo test -p brainflow-graph`
Run TS: typecheck graph model via desktop `npm run typecheck`.
