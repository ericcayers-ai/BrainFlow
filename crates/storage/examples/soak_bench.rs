//! Timed FTS / search / open metrics for large vaults.
//!
//! ```bash
//! cargo run -p brainflow-storage --example soak_bench -- 10000
//! BRAINFLOW_SOAK_N=1000 cargo run -p brainflow-storage --example soak_bench
//! ```
//!
//! Writes Markdown notes under `--vault` (default: tempdir), indexes into a local
//! SQLite catalog (never inside a OneDrive-synced vault root in production), and
//! reports p50/p95 latencies for warm FTS MATCH, tag search, and note open (meta + body read).

use brainflow_storage::{list_indexed_paths, open_catalog, search_notes, search_notes_detailed, upsert_note_enriched};
use std::env;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::Instant;

fn percentile(sorted_ms: &[f64], p: f64) -> f64 {
    if sorted_ms.is_empty() {
        return 0.0;
    }
    let rank = ((p / 100.0) * (sorted_ms.len() as f64 - 1.0)).round() as usize;
    sorted_ms[rank.min(sorted_ms.len() - 1)]
}

fn summarize(label: &str, samples_ms: &mut [f64]) -> (f64, f64, f64) {
    samples_ms.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mean = samples_ms.iter().sum::<f64>() / samples_ms.len().max(1) as f64;
    let p50 = percentile(samples_ms, 50.0);
    let p95 = percentile(samples_ms, 95.0);
    println!("{label}: n={} mean={mean:.3}ms p50={p50:.3}ms p95={p95:.3}ms", samples_ms.len());
    (mean, p50, p95)
}

fn parse_n() -> usize {
    if let Ok(v) = env::var("BRAINFLOW_SOAK_N") {
        if let Ok(n) = v.trim().parse::<usize>() {
            return n.max(1);
        }
    }
    env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(10_000)
        .max(1)
}

fn vault_root() -> PathBuf {
    if let Ok(p) = env::var("BRAINFLOW_SOAK_VAULT") {
        return PathBuf::from(p);
    }
    // Prefer an env override; fall back to a sibling of the binary cwd.
    env::temp_dir().join(format!("brainflow-soak-{}", std::process::id()))
}

fn write_note(vault: &Path, i: usize) -> (PathBuf, String, String, String) {
    let folder = vault.join("notes").join(format!("batch{:03}", i / 100));
    fs::create_dir_all(&folder).expect("mkdir");
    let name = format!("note-{i:05}.md");
    let path = folder.join(&name);
    let rel = format!("notes/batch{:03}/{name}", i / 100);
    let title = format!("Soak note {i}");
    let tags = match i % 7 {
        0 => "study,plan",
        1 => "research",
        2 => "ops,sop",
        3 => "teaching",
        4 => "meeting",
        5 => "creative",
        _ => "pkm,inbox",
    };
    let body = format!(
        "---\ntitle: \"{title}\"\ntags: [{tags}]\n---\n\n# {title}\n\n\
         BrainFlow soak corpus note {i}. Unique token SOAKTOKEN{i} for FTS.\n\n\
         ## Section A\n\nWorkflow graph layout and search latency probe.\n\n\
         ## Section B\n\nLorem linked to [[note-{:05}]] and topic keywords mitochondria flashcards.\n",
        (i + 1) % 10_000
    );
    let mut f = fs::File::create(&path).expect("create note");
    f.write_all(body.as_bytes()).expect("write");
    (path, rel, title, tags.to_string())
}

fn main() {
    let n = parse_n();
    let vault = vault_root();
    let catalog_dir = env::var("BRAINFLOW_SOAK_CATALOG")
        .map(PathBuf::from)
        .unwrap_or_else(|_| vault.join(".brainflow-local-catalog"));
    fs::create_dir_all(&vault).expect("vault");
    fs::create_dir_all(&catalog_dir).expect("catalog dir");
    let db_path = catalog_dir.join("index.sqlite");

    println!("BrainFlow 10k-style soak bench");
    println!("  N={n}");
    println!("  vault={}", vault.display());
    println!("  catalog={}", db_path.display());

    let t0 = Instant::now();
    let conn = open_catalog(&db_path).expect("open catalog");
    let mut rel_paths: Vec<String> = Vec::with_capacity(n);
    for i in 0..n {
        let (_abs, rel, title, tags) = write_note(&vault, i);
        let abs = vault.join(&rel);
        let body = fs::read_to_string(&abs).expect("read");
        let hash = format!("sha256:soak:{i}");
        upsert_note_enriched(
            &conn,
            &format!("id-{i}"),
            &rel,
            &hash,
            "2026-07-16T00:00:00Z",
            &body,
            &title,
            &tags,
        )
        .expect("upsert");
        rel_paths.push(rel);
        if (i + 1) % 1000 == 0 || i + 1 == n {
            println!("  indexed {}/{}", i + 1, n);
        }
    }
    let index_ms = t0.elapsed().as_secs_f64() * 1000.0;
    let indexed = list_indexed_paths(&conn).expect("list");
    assert_eq!(indexed.len(), n, "index count mismatch — data loss during generate");
    println!("index_build_ms={index_ms:.1} counted={}", indexed.len());

    // Warm FTS (single-token unique + common term)
    let queries: Vec<String> = vec![
        "workflow".into(),
        "mitochondria".into(),
        "SOAKTOKEN42".into(),
        "flashcards".into(),
        format!("SOAKTOKEN{}", n / 2),
        "BrainFlow".into(),
        "Section".into(),
        "layout".into(),
    ];
    // Warm-up
    for q in &queries {
        let _ = search_notes(&conn, q).unwrap();
    }

    let rounds = 40usize.max(8);
    let mut fts_ms = Vec::with_capacity(rounds);
    for r in 0..rounds {
        let q = &queries[r % queries.len()];
        let start = Instant::now();
        let hits = search_notes(&conn, q).expect("fts");
        let _ = hits.len();
        fts_ms.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    let (_m, fts_p50, fts_p95) = summarize("fts_warm_match", &mut fts_ms);

    let mut tag_ms = Vec::with_capacity(rounds);
    for r in 0..rounds {
        let q = if r % 2 == 0 { "tag:study" } else { "tag:research" };
        let start = Instant::now();
        let hits = search_notes_detailed(&conn, q).expect("tag");
        let _ = hits.len();
        tag_ms.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    let (_m, tag_p50, tag_p95) = summarize("tag_search", &mut tag_ms);

    // Quick-switcher style: path substring isn't FTS here — time MATCH on title-ish token + open body
    let mut open_ms = Vec::with_capacity(rounds);
    for r in 0..rounds {
        let rel = &rel_paths[r * (n / rounds).max(1) % n];
        let abs = vault.join(rel);
        let start = Instant::now();
        // "open": meta presence already indexed; read body from vault (editor open path)
        let body = fs::read_to_string(&abs).expect("open body");
        assert!(!body.is_empty());
        open_ms.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    let (_m, open_p50, open_p95) = summarize("note_open_read", &mut open_ms);

    // Quick switcher proxy: FTS on unique tokens (hyphenated note-NNNNN needs quoting)
    let mut qs_ms = Vec::with_capacity(rounds);
    for r in 0..rounds {
        let token = format!("SOAKTOKEN{}", (r * 97) % n);
        let start = Instant::now();
        let hits = search_notes(&conn, &token).expect("qs");
        let _ = hits.first();
        qs_ms.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    let (_m, qs_p50, qs_p95) = summarize("quick_switcher_proxy_fts", &mut qs_ms);

    // Editor input-latency *proxy*: open + atomic-style re-upsert (save) + FTS hit.
    // Not WebView/CodeMirror keystroke timing — catalog path that backs autosave/search.
    let mut cycle_ms = Vec::with_capacity(rounds);
    let mut save_ms = Vec::with_capacity(rounds);
    for r in 0..rounds {
        let i = (r * 131) % n;
        let rel = &rel_paths[i];
        let abs = vault.join(rel);
        let title = format!("Soak note {i}");
        let tags = "study,plan";
        let start = Instant::now();
        let mut body = fs::read_to_string(&abs).expect("cycle open");
        body.push_str(&format!("\n\n<!-- edit-cycle {r} EDITMARKER{r} -->\n"));
        let t_save = Instant::now();
        fs::write(&abs, &body).expect("cycle write");
        upsert_note_enriched(
            &conn,
            &format!("id-{i}"),
            rel,
            &format!("sha256:soak:edit:{i}:{r}"),
            "2026-07-16T00:00:01Z",
            &body,
            &title,
            tags,
        )
        .expect("cycle upsert");
        save_ms.push(t_save.elapsed().as_secs_f64() * 1000.0);
        let hits = search_notes(&conn, &format!("EDITMARKER{r}")).expect("cycle fts");
        assert!(
            hits.iter().any(|p| p == rel),
            "edit-cycle search miss — data loss after save"
        );
        cycle_ms.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    let (_m, save_p50, save_p95) = summarize("note_save_upsert", &mut save_ms);
    let (_m, cycle_p50, cycle_p95) = summarize("open_save_search_cycle", &mut cycle_ms);

    let budget_fts_p95 = 100.0;
    // Catalog proxy for editor path responsiveness (docs/PERFORMANCE_BUDGETS §1 keystroke is UI).
    let budget_cycle_p95 = 50.0;
    let fts_ok = fts_p95 < budget_fts_p95;
    let qs_ok = qs_p95 < budget_fts_p95;
    let cycle_ok = cycle_p95 < budget_cycle_p95;
    let save_ok = save_p95 < budget_cycle_p95;
    println!();
    println!("budgets: search/quick_switcher p95 < {budget_fts_p95} ms; open+save+search cycle p95 < {budget_cycle_p95} ms");
    println!("fts_p95_ok={fts_ok} qs_p95_ok={qs_ok} cycle_p95_ok={cycle_ok} save_p95_ok={save_ok}");
    println!(
        "RESULT_JSON {{\"n\":{n},\"index_build_ms\":{index_ms:.1},\"fts_p50_ms\":{fts_p50:.3},\"fts_p95_ms\":{fts_p95:.3},\"tag_p50_ms\":{tag_p50:.3},\"tag_p95_ms\":{tag_p95:.3},\"open_p50_ms\":{open_p50:.3},\"open_p95_ms\":{open_p95:.3},\"qs_p50_ms\":{qs_p50:.3},\"qs_p95_ms\":{qs_p95:.3},\"save_p50_ms\":{save_p50:.3},\"save_p95_ms\":{save_p95:.3},\"cycle_p50_ms\":{cycle_p50:.3},\"cycle_p95_ms\":{cycle_p95:.3},\"fts_budget_ok\":{fts_ok},\"qs_budget_ok\":{qs_ok},\"cycle_budget_ok\":{cycle_ok},\"save_budget_ok\":{save_ok},\"data_loss\":false}}"
    );

    if env::var("BRAINFLOW_SOAK_KEEP").ok().as_deref() != Some("1") {
        // Leave vault if KEEP; otherwise best-effort cleanup of temp vault only.
        if vault.starts_with(env::temp_dir()) {
            let _ = fs::remove_dir_all(&vault);
        }
    }
}
