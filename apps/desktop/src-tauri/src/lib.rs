mod sync_cmds;

use brainflow_app_core::redact::{redact_line, redact_path};
use chrono::Utc;
use serde::Serialize;
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri_plugin_dialog::DialogExt;
use uuid::Uuid;

struct AppState {
    vault_root: Mutex<Option<PathBuf>>,
}

/// Map any error to a user-facing string with secrets/paths redacted for logs.
fn err_msg(e: impl std::fmt::Display) -> String {
    redact_line(&e.to_string())
}

fn log_warn(context: &str, detail: &str) {
    eprintln!("[brainflow] {context}: {}", redact_line(detail));
}

#[derive(Debug, Serialize)]
struct VaultOpenResult {
    root: String,
    onedrive_warning: bool,
}

#[derive(Debug, Serialize)]
struct LlmHealth {
    ok: bool,
    detail: Value,
}

#[derive(Debug, Serialize)]
struct GenerateResult {
    workflow: Value,
    run: Value,
    artifact_path: String,
}

fn repo_root() -> PathBuf {
    // apps/desktop/src-tauri -> repo root
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.."))
}

fn worker_dir() -> PathBuf {
    repo_root().join("services/ai-worker")
}

fn catalog_db_path() -> PathBuf {
    let base = dirs::data_local_dir().unwrap_or_else(|| PathBuf::from("."));
    base.join("BrainFlow").join("indexes").join("catalog.sqlite")
}

fn require_vault_root(state: &tauri::State<'_, AppState>) -> Result<PathBuf, String> {
    state
        .vault_root
        .lock()
        .map_err(err_msg)?
        .clone()
        .ok_or_else(|| "No vault open".into())
}

fn index_note_body(relative_path: &str, content: &str) {
    let Ok(conn) = brainflow_storage::open_catalog(&catalog_db_path()) else {
        return;
    };
    let analysis = brainflow_vault::analyze_note(relative_path, content);
    let hash = brainflow_vault::content_hash(content.as_bytes());
    let tags = analysis.tags.join(",");
    let _ = brainflow_storage::upsert_note_enriched(
        &conn,
        &Uuid::new_v4().to_string(),
        relative_path,
        &hash,
        &Utc::now().to_rfc3339(),
        content,
        &analysis.title_guess,
        &tags,
    );
}

fn reindex_vault(root: &std::path::Path) -> Result<usize, String> {
    let conn = brainflow_storage::open_catalog(&catalog_db_path()).map_err(|e| e.to_string())?;
    let notes = brainflow_vault::list_note_paths(root).map_err(|e| e.to_string())?;
    let mut n = 0usize;
    for path in notes {
        if let Ok(content) = brainflow_vault::read_text(root, &path) {
            let analysis = brainflow_vault::analyze_note(&path, &content);
            let hash = brainflow_vault::content_hash(content.as_bytes());
            let tags = analysis.tags.join(",");
            let _ = brainflow_storage::upsert_note_enriched(
                &conn,
                &Uuid::new_v4().to_string(),
                &path,
                &hash,
                &Utc::now().to_rfc3339(),
                &content,
                &analysis.title_guess,
                &tags,
            );
            n += 1;
        }
    }
    Ok(n)
}

fn python_cmd() -> Command {
    if let Ok(custom) = std::env::var("BRAINFLOW_PYTHON") {
        return Command::new(custom);
    }
    let venv_py = worker_dir().join(if cfg!(windows) {
        ".venv/Scripts/python.exe"
    } else {
        ".venv/bin/python"
    });
    if venv_py.exists() {
        return Command::new(venv_py);
    }
    // Windows: `py` launcher is optional; prefer `python` on PATH.
    if cfg!(windows) {
        return Command::new("python");
    }
    Command::new("python3")
}

fn rpc_call(method: &str, params: Value) -> Result<Value, String> {
    let id = Uuid::new_v4().to_string();
    let req = json!({
        "jsonrpc": "2.0",
        "id": id,
        "method": method,
        "params": params,
    });
    let mut child = python_cmd()
        .arg("-m")
        .arg("brainflow_worker")
        .current_dir(worker_dir())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| {
            err_msg(format!("failed to spawn AI worker (is the venv installed?): {e}"))
        })?;

    {
        let stdin = child.stdin.as_mut().ok_or("worker stdin missing")?;
        writeln!(stdin, "{}", req).map_err(err_msg)?;
    }
    drop(child.stdin.take());

    let stdout = child.stdout.take().ok_or("worker stdout missing")?;
    let stderr = child.stderr.take();
    let mut lines = BufReader::new(stdout).lines();
    let line = match lines.next() {
        Some(Ok(line)) => line,
        Some(Err(e)) => return Err(err_msg(e)),
        None => {
            let err = stderr
                .and_then(|s| {
                    let mut buf = String::new();
                    let mut r = BufReader::new(s);
                    r.read_to_string(&mut buf).ok()?;
                    Some(buf)
                })
                .unwrap_or_default();
            let _ = child.wait();
            log_warn("worker_rpc", &err);
            return Err(err_msg(format!(
                "worker produced no response. stderr={}",
                redact_line(&err)
            )));
        }
    };

    let _ = child.kill();
    let _ = child.wait();

    let resp: Value = serde_json::from_str(&line).map_err(|e| format!("bad rpc json: {e}"))?;
    if let Some(err) = resp.get("error") {
        return Err(err.to_string());
    }
    resp.get("result")
        .cloned()
        .ok_or_else(|| "rpc missing result".into())
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("BrainFlow core ready, {name}")
}

#[tauri::command]
async fn pick_vault(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = app
        .dialog()
        .file()
        .set_title("Open BrainFlow vault")
        .blocking_pick_folder();
    Ok(path.map(|p| match p {
        tauri_plugin_dialog::FilePath::Path(path) => path.display().to_string(),
        tauri_plugin_dialog::FilePath::Url(url) => url.to_string(),
    }))
}

#[tauri::command]
fn open_vault(
    state: tauri::State<'_, AppState>,
    sync: tauri::State<'_, sync_cmds::SyncState>,
    path: String,
) -> Result<VaultOpenResult, String> {
    let info = brainflow_vault::open_vault(&path).map_err(err_msg)?;
    log_warn(
        "open_vault",
        &redact_path(&info.root.display().to_string(), None),
    );
    // Local catalog in OS app data (not inside vault / OneDrive).
    let db = catalog_db_path();
    let _conn = brainflow_storage::open_catalog(&db).map_err(err_msg)?;
    let _ = reindex_vault(&info.root);
    let result = VaultOpenResult {
        root: info.root.display().to_string(),
        onedrive_warning: info.onedrive_warning,
    };
    *state.vault_root.lock().map_err(err_msg)? = Some(info.root.clone());
    let _ = sync_cmds::attach_vault(&sync, &info.root)?;
    Ok(result)
}

#[tauri::command]
async fn create_vault_dialog(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = app
        .dialog()
        .file()
        .set_title("Create BrainFlow vault")
        .blocking_pick_folder();
    Ok(path.map(|p| match p {
        tauri_plugin_dialog::FilePath::Path(path) => path.display().to_string(),
        tauri_plugin_dialog::FilePath::Url(url) => url.to_string(),
    }))
}

#[tauri::command]
fn create_vault(
    state: tauri::State<'_, AppState>,
    sync: tauri::State<'_, sync_cmds::SyncState>,
    path: String,
    display_name: Option<String>,
) -> Result<VaultOpenResult, String> {
    let name = display_name.unwrap_or_else(|| "BrainFlow Vault".into());
    let info = brainflow_vault::create_vault(&path, &name).map_err(|e| e.to_string())?;
    let _ = brainflow_storage::open_catalog(&catalog_db_path()).map_err(|e| e.to_string())?;
    let result = VaultOpenResult {
        root: info.root.display().to_string(),
        onedrive_warning: info.onedrive_warning,
    };
    *state.vault_root.lock().map_err(|e| e.to_string())? = Some(info.root.clone());
    let _ = sync_cmds::attach_vault(&sync, &info.root)?;
    Ok(result)
}

#[tauri::command]
fn list_vault_dir(
    state: tauri::State<'_, AppState>,
    relative_path: Option<String>,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let rel = relative_path.unwrap_or_default();
    let entries = brainflow_vault::list_dir(&root, &rel).map_err(|e| e.to_string())?;
    serde_json::to_value(entries).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_notes(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let notes = brainflow_vault::list_notes_for_switcher(&root).map_err(|e| e.to_string())?;
    serde_json::to_value(notes).map_err(|e| e.to_string())
}

#[tauri::command]
fn create_note(
    state: tauri::State<'_, AppState>,
    relative_path: String,
    content: Option<String>,
) -> Result<(), String> {
    let root = require_vault_root(&state)?;
    let body = content.unwrap_or_else(|| format!("# {}\n\n", relative_path));
    brainflow_vault::create_note(&root, &relative_path, &body).map_err(|e| e.to_string())?;
    index_note_body(&relative_path, &body);
    Ok(())
}

#[tauri::command]
fn read_note(state: tauri::State<'_, AppState>, relative_path: String) -> Result<String, String> {
    let root = require_vault_root(&state)?;
    brainflow_vault::read_text(&root, &relative_path).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_note(
    state: tauri::State<'_, AppState>,
    sync: tauri::State<'_, sync_cmds::SyncState>,
    relative_path: String,
    content: String,
) -> Result<(), String> {
    let root = require_vault_root(&state)?;
    brainflow_vault::save_note(&root, &relative_path, &content).map_err(|e| e.to_string())?;
    index_note_body(&relative_path, &content);
    // Debounced sync path — never invoked by LLM tools.
    let _ = with_engine_soft(&sync, |eng| {
        eng.on_fs_change();
        let _ = eng.tick();
    });
    Ok(())
}

fn with_engine_soft(sync: &sync_cmds::SyncState, f: impl FnOnce(&mut brainflow_sync::SyncEngine)) {
    if let Ok(mut guard) = sync.engine.lock() {
        if let Some(eng) = guard.as_mut() {
            f(eng);
        }
    }
}

#[tauri::command]
fn note_stat(state: tauri::State<'_, AppState>, relative_path: String) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let stat = brainflow_vault::note_stat(&root, &relative_path).map_err(|e| e.to_string())?;
    serde_json::to_value(stat).map_err(|e| e.to_string())
}

#[tauri::command]
fn analyze_note_cmd(
    state: tauri::State<'_, AppState>,
    relative_path: String,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let content = brainflow_vault::read_text(&root, &relative_path).map_err(|e| e.to_string())?;
    let analysis = brainflow_vault::analyze_note(&relative_path, &content);
    serde_json::to_value(analysis).map_err(|e| e.to_string())
}

#[tauri::command]
fn note_links(state: tauri::State<'_, AppState>, relative_path: String) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let links = brainflow_vault::links_for_note(&root, &relative_path).map_err(|e| e.to_string())?;
    serde_json::to_value(links).map_err(|e| e.to_string())
}

#[tauri::command]
fn vault_tags(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let tags = brainflow_vault::list_tags(&root).map_err(|e| e.to_string())?;
    serde_json::to_value(tags).map_err(|e| e.to_string())
}

#[tauri::command]
fn search_vault(state: tauri::State<'_, AppState>, query: String) -> Result<Value, String> {
    let _root = require_vault_root(&state)?;
    let conn = brainflow_storage::open_catalog(&catalog_db_path()).map_err(|e| e.to_string())?;
    let hits =
        brainflow_storage::search_notes_detailed(&conn, &query).map_err(|e| e.to_string())?;
    serde_json::to_value(hits).map_err(|e| e.to_string())
}

#[tauri::command]
fn reindex_notes(state: tauri::State<'_, AppState>) -> Result<usize, String> {
    let root = require_vault_root(&state)?;
    reindex_vault(&root)
}

#[tauri::command]
fn knowledge_graph(
    state: tauri::State<'_, AppState>,
    focus_path: Option<String>,
    local_only: Option<bool>,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let notes = brainflow_vault::list_note_paths(&root).map_err(|e| e.to_string())?;
    let (links, _) = brainflow_vault::collect_all_links(&root).map_err(|e| e.to_string())?;
    let pairs: Vec<(String, String)> = links
        .into_iter()
        .filter_map(|l| l.to_path.map(|to| (l.from_path, to)))
        .collect();
    let local = local_only.unwrap_or(false);
    let projection = brainflow_graph::knowledge_projection_from_links(
        &notes,
        &pairs,
        focus_path.as_deref(),
        local,
    );
    serde_json::to_value(projection).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_note_snapshots(
    state: tauri::State<'_, AppState>,
    relative_path: String,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let snaps =
        brainflow_vault::list_snapshots(&root, &relative_path).map_err(|e| e.to_string())?;
    serde_json::to_value(snaps).map_err(|e| e.to_string())
}

#[tauri::command]
fn restore_note_snapshot(
    state: tauri::State<'_, AppState>,
    relative_path: String,
    snapshot_id: String,
) -> Result<String, String> {
    let root = require_vault_root(&state)?;
    let content = brainflow_vault::restore_snapshot(&root, &relative_path, &snapshot_id)
        .map_err(|e| e.to_string())?;
    index_note_body(&relative_path, &content);
    Ok(content)
}

#[tauri::command]
fn list_vault_templates(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let t = brainflow_vault::list_templates(&root).map_err(|e| e.to_string())?;
    serde_json::to_value(t).map_err(|e| e.to_string())
}

#[tauri::command]
fn apply_note_template(
    state: tauri::State<'_, AppState>,
    template_id: String,
    dest_relative: String,
    title: String,
) -> Result<String, String> {
    let root = require_vault_root(&state)?;
    let body = brainflow_vault::apply_template(&root, &template_id, &dest_relative, &title)
        .map_err(|e| e.to_string())?;
    index_note_body(&dest_relative, &body);
    Ok(body)
}

#[tauri::command]
fn open_daily_note(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let (path, content) =
        brainflow_vault::open_or_create_daily_note(&root).map_err(|e| e.to_string())?;
    index_note_body(&path, &content);
    Ok(json!({ "path": path, "content": content }))
}

#[tauri::command]
fn create_unique_note(
    state: tauri::State<'_, AppState>,
    title: Option<String>,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let (path, content) =
        brainflow_vault::create_unique_note(&root, title.as_deref()).map_err(|e| e.to_string())?;
    index_note_body(&path, &content);
    Ok(json!({ "path": path, "content": content }))
}

#[tauri::command]
fn random_note(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let path = brainflow_vault::random_note_path(&root).map_err(|e| e.to_string())?;
    Ok(json!({ "path": path }))
}

#[tauri::command]
fn list_bookmarks(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let store = brainflow_vault::load_bookmarks(&root).map_err(|e| e.to_string())?;
    serde_json::to_value(store).map_err(|e| e.to_string())
}

#[tauri::command]
fn toggle_bookmark(
    state: tauri::State<'_, AppState>,
    relative_path: String,
    title: Option<String>,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let title = title.unwrap_or_default();
    let store = brainflow_vault::toggle_bookmark(&root, &relative_path, &title)
        .map_err(|e| e.to_string())?;
    serde_json::to_value(store).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_workspace_layouts(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let list = brainflow_vault::list_workspaces(&root).map_err(|e| e.to_string())?;
    serde_json::to_value(list).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_workspace_layout(
    state: tauri::State<'_, AppState>,
    layout: Value,
) -> Result<String, String> {
    let root = require_vault_root(&state)?;
    let layout: brainflow_vault::WorkspaceLayout =
        serde_json::from_value(layout).map_err(|e| e.to_string())?;
    brainflow_vault::save_workspace(&root, &layout).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_workspace_layout(
    state: tauri::State<'_, AppState>,
    id: String,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let layout = brainflow_vault::load_workspace(&root, &id).map_err(|e| e.to_string())?;
    serde_json::to_value(layout).map_err(|e| e.to_string())
}

#[tauri::command]
fn delete_workspace_layout(state: tauri::State<'_, AppState>, id: String) -> Result<(), String> {
    let root = require_vault_root(&state)?;
    brainflow_vault::delete_workspace(&root, &id).map_err(|e| e.to_string())
}

#[tauri::command]
fn property_suggestions(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let suggestions =
        brainflow_vault::property_schema_suggestions(&root).map_err(|e| e.to_string())?;
    serde_json::to_value(suggestions).map_err(|e| e.to_string())
}

#[tauri::command]
fn set_note_property(
    state: tauri::State<'_, AppState>,
    sync: tauri::State<'_, sync_cmds::SyncState>,
    relative_path: String,
    key: String,
    value: String,
) -> Result<String, String> {
    let root = require_vault_root(&state)?;
    let content = brainflow_vault::set_note_property(&root, &relative_path, &key, &value)
        .map_err(|e| e.to_string())?;
    index_note_body(&relative_path, &content);
    let _ = with_engine_soft(&sync, |eng| {
        eng.on_fs_change();
        let _ = eng.tick();
    });
    Ok(content)
}

#[tauri::command]
fn ensure_foundations(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let paths =
        brainflow_vault::ensure_bases_canvas_foundations(&root).map_err(|e| e.to_string())?;
    serde_json::to_value(paths).map_err(|e| e.to_string())
}

#[tauri::command]
fn rename_note(
    state: tauri::State<'_, AppState>,
    sync: tauri::State<'_, sync_cmds::SyncState>,
    from_path: String,
    to_path: String,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let result =
        brainflow_vault::rename_note(&root, &from_path, &to_path).map_err(|e| e.to_string())?;
    let _ = reindex_vault(&root);
    let _ = with_engine_soft(&sync, |eng| {
        eng.on_fs_change();
        let _ = eng.tick();
    });
    serde_json::to_value(result).map_err(|e| e.to_string())
}

#[tauri::command]
fn base_table(
    state: tauri::State<'_, AppState>,
    base_path: Option<String>,
    filter_column: Option<String>,
    filter_value: Option<String>,
    sort_column: Option<String>,
    sort_direction: Option<String>,
) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let filters = match (filter_column, filter_value) {
        (Some(col), Some(val)) if !val.is_empty() => Some(vec![brainflow_vault::BaseFilter {
            column: col,
            op: "contains".into(),
            value: val,
        }]),
        _ => None,
    };
    let sorts = sort_column.map(|col| {
        vec![brainflow_vault::BaseSort {
            column: col,
            direction: sort_direction.unwrap_or_else(|| "asc".into()),
        }]
    });
    let (def, rows) = brainflow_vault::base_rows(
        &root,
        base_path.as_deref(),
        filters.as_deref(),
        sorts.as_deref(),
    )
    .map_err(|e| e.to_string())?;
    Ok(json!({ "definition": def, "rows": rows }))
}

#[tauri::command]
fn save_base_definition(
    state: tauri::State<'_, AppState>,
    relative_path: String,
    definition: Value,
) -> Result<(), String> {
    let root = require_vault_root(&state)?;
    let def: brainflow_vault::BaseDefinition =
        serde_json::from_value(definition).map_err(|e| e.to_string())?;
    brainflow_vault::save_base(&root, &relative_path, &def).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_canvases(state: tauri::State<'_, AppState>) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let list = brainflow_vault::list_canvases(&root).map_err(|e| e.to_string())?;
    serde_json::to_value(list).map_err(|e| e.to_string())
}

#[tauri::command]
fn read_canvas(state: tauri::State<'_, AppState>, relative_path: String) -> Result<Value, String> {
    let root = require_vault_root(&state)?;
    let doc = brainflow_vault::read_canvas(&root, &relative_path).map_err(|e| e.to_string())?;
    serde_json::to_value(doc).map_err(|e| e.to_string())
}

#[tauri::command]
fn write_canvas(
    state: tauri::State<'_, AppState>,
    sync: tauri::State<'_, sync_cmds::SyncState>,
    relative_path: String,
    document: Value,
) -> Result<(), String> {
    let root = require_vault_root(&state)?;
    let doc: brainflow_vault::CanvasDoc =
        serde_json::from_value(document).map_err(|e| e.to_string())?;
    brainflow_vault::write_canvas(&root, &relative_path, &doc).map_err(|e| e.to_string())?;
    let _ = with_engine_soft(&sync, |eng| {
        eng.on_fs_change();
        let _ = eng.tick();
    });
    Ok(())
}

#[tauri::command]
fn import_dropped_text(
    state: tauri::State<'_, AppState>,
    sync: tauri::State<'_, sync_cmds::SyncState>,
    dest_relative: String,
    content: String,
) -> Result<String, String> {
    let root = require_vault_root(&state)?;
    let rel = brainflow_vault::import_text_file(&root, &dest_relative, &content)
        .map_err(|e| e.to_string())?;
    if rel.to_ascii_lowercase().ends_with(".md") {
        index_note_body(&rel, &content);
    }
    let _ = with_engine_soft(&sync, |eng| {
        eng.on_fs_change();
        let _ = eng.tick();
    });
    Ok(rel)
}

#[tauri::command]
fn llm_health() -> Result<LlmHealth, String> {
    let detail = rpc_call("llm.health", json!({}))?;
    let ok = detail.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
    Ok(LlmHealth { ok, detail })
}

#[tauri::command]
fn model_recommend(
    policy: Option<String>,
    requirements: Option<Value>,
    pinned: Option<Value>,
) -> Result<Value, String> {
    rpc_call(
        "llm.recommend",
        json!({
            "policy": policy.unwrap_or_else(|| "auto".into()),
            "requirements": requirements.unwrap_or(json!({})),
            "pinned": pinned,
            "run_active": false,
        }),
    )
}

#[tauri::command]
fn model_hardware() -> Result<Value, String> {
    rpc_call("llm.hardware", json!({}))
}

#[tauri::command]
fn model_registry_status(refresh: Option<bool>) -> Result<Value, String> {
    rpc_call(
        "registry.load",
        json!({ "refresh": refresh.unwrap_or(false) }),
    )
}

/// Store a provider API key via the worker secret facade (OS keyring when available).
/// Never write secrets into the portable vault.
#[tauri::command]
fn model_set_secret(ref_name: String, value: String) -> Result<Value, String> {
    if value.is_empty() {
        return Err("empty secret rejected".into());
    }
    rpc_call(
        "secrets.set",
        json!({ "ref": ref_name, "value": value }),
    )
}

#[tauri::command]
fn generate_workflow_slice(
    state: tauri::State<'_, AppState>,
    prompt: String,
    note_relative_path: String,
) -> Result<GenerateResult, String> {
    let root = state
        .vault_root
        .lock()
        .map_err(|e| e.to_string())?
        .clone()
        .ok_or("No vault open")?;

    let source_text = brainflow_vault::read_text(&root, &note_relative_path)
        .unwrap_or_else(|_| String::new());

    let result = rpc_call(
        "workflow.generate",
        json!({
            "prompt": prompt,
            "source_text": source_text,
        }),
    )?;

    let workflow = result
        .get("workflow")
        .cloned()
        .ok_or("worker returned no workflow")?;
    brainflow_policy::require_workflow_schema_v1(&workflow).map_err(|e| e.to_string())?;
    let policy = brainflow_policy::validate_workflow_policy(&workflow);
    if !policy.ok {
        return Err(format!("policy rejected: {}", policy.errors.join("; ")));
    }
    brainflow_policy::assert_safe_overlay_path(&format!(
        ".brainflow/artifacts/{}/placeholder.md",
        workflow
            .get("workflow_id")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
    ))
    .map_err(|e| e.to_string())?;

    // Persist workflow
    let workflow_id = workflow
        .get("workflow_id")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    let wf_rel = format!(".brainflow/workflows/{workflow_id}.json");
    let wf_path = brainflow_vault::resolve_in_vault(&root, &wf_rel).map_err(|e| e.to_string())?;
    brainflow_vault::atomic_write_json(&wf_path, &workflow).map_err(|e| e.to_string())?;

    // Canonical graph projection under .brainflow/graphs
    if let Ok(graph) = brainflow_graph::graph_from_workflow(&workflow) {
        let g_rel = format!(".brainflow/graphs/{workflow_id}.json");
        if let Ok(g_path) = brainflow_vault::resolve_in_vault(&root, &g_rel) {
            let _ = brainflow_vault::atomic_write_json(
                &g_path,
                &serde_json::to_value(&graph).unwrap_or(json!({})),
            );
        }
    }

    // Derived Markdown artifact (safe overlay only)
    let run_id = Uuid::new_v4();
    let artifact_rel = format!(".brainflow/artifacts/{workflow_id}/{run_id}/summary.md");
    brainflow_policy::assert_safe_overlay_path(&artifact_rel).map_err(|e| e.to_string())?;
    let artifact_path =
        brainflow_vault::resolve_in_vault(&root, &artifact_rel).map_err(|e| e.to_string())?;
    let title = workflow
        .get("title")
        .and_then(|v| v.as_str())
        .unwrap_or("Workflow");
    let goal = workflow
        .pointer("/goal/statement")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let artifact = format!(
        "# {title}\n\nGenerated by BrainFlow workflow kernel.\n\n## Goal\n\n{goal}\n\n## Source\n\n`{note_relative_path}`\n\n## Workflow ID\n\n`{workflow_id}`\n\n## Run ID\n\n`{run_id}`\n"
    );
    brainflow_vault::atomic_write_text(&artifact_path, &artifact).map_err(|e| e.to_string())?;

    let run = json!({
        "schema_version": 1,
        "run_id": run_id,
        "workflow_id": workflow_id,
        "status": "succeeded",
        "created_at": Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true),
        "updated_at": Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true),
        "vault_relative_workflow_path": wf_rel,
        "artifact_paths": [artifact_rel],
        "llm": result.get("workflow").and_then(|w| w.pointer("/pins/models/planner")).cloned(),
        "provenance": result.get("kernel").and_then(|k| k.get("provenance")).cloned(),
        "kernel_stages": result.get("kernel").and_then(|k| k.get("stages")).cloned(),
        "error": null
    });
    let run_rel = format!(".brainflow/runs/{run_id}.json");
    let run_path = brainflow_vault::resolve_in_vault(&root, &run_rel).map_err(|e| e.to_string())?;
    brainflow_vault::atomic_write_json(&run_path, &run).map_err(|e| e.to_string())?;

    // Session pointer for reopen
    let session = json!({
        "schema_version": 1,
        "last_vault": root.display().to_string(),
        "last_note": note_relative_path,
        "last_run_id": run_id,
        "last_workflow_id": workflow_id,
    });
    let session_path = dirs::data_local_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("BrainFlow")
        .join("session.json");
    if let Some(parent) = session_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    brainflow_vault::atomic_write_json(&session_path, &session).map_err(|e| e.to_string())?;

    Ok(GenerateResult {
        workflow,
        run,
        artifact_path: artifact_rel,
    })
}

#[tauri::command]
fn load_session(
    state: tauri::State<'_, AppState>,
    sync: tauri::State<'_, sync_cmds::SyncState>,
) -> Result<Value, String> {
    let session_path = dirs::data_local_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("BrainFlow")
        .join("session.json");
    if !session_path.exists() {
        return Ok(json!({ "ok": false, "reason": "no session" }));
    }
    let text = std::fs::read_to_string(&session_path).map_err(|e| e.to_string())?;
    let session: Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;
    if let Some(vault) = session.get("last_vault").and_then(|v| v.as_str()) {
        let info = brainflow_vault::open_vault(vault).map_err(|e| e.to_string())?;
        *state.vault_root.lock().map_err(|e| e.to_string())? = Some(info.root.clone());
        let _ = sync_cmds::attach_vault(&sync, &info.root);
        let mut out = session;
        if let Some(obj) = out.as_object_mut() {
            obj.insert("ok".into(), json!(true));
            obj.insert("onedrive_warning".into(), json!(info.onedrive_warning));
            if let Some(wf_id) = obj.get("last_workflow_id").and_then(|v| v.as_str()) {
                let rel = format!(".brainflow/workflows/{wf_id}.json");
                if let Ok(wf) = brainflow_vault::read_text(&info.root, &rel) {
                    if let Ok(parsed) = serde_json::from_str::<Value>(&wf) {
                        obj.insert("workflow".into(), parsed);
                    }
                }
            }
            if let Some(run_id) = obj.get("last_run_id").and_then(|v| v.as_str()) {
                let rel = format!(".brainflow/runs/{run_id}.json");
                if let Ok(run) = brainflow_vault::read_text(&info.root, &rel) {
                    if let Ok(parsed) = serde_json::from_str::<Value>(&run) {
                        obj.insert("run".into(), parsed);
                    }
                }
            }
            if let Some(note) = obj.get("last_note").and_then(|v| v.as_str()) {
                if let Ok(content) = brainflow_vault::read_text(&info.root, note) {
                    obj.insert("note_content".into(), json!(content));
                }
            }
        }
        return Ok(out);
    }
    Ok(json!({ "ok": false, "reason": "session missing vault" }))
}

#[tauri::command]
fn list_runs(state: tauri::State<'_, AppState>) -> Result<Vec<String>, String> {
    let root = state
        .vault_root
        .lock()
        .map_err(|e| e.to_string())?
        .clone()
        .ok_or("No vault open")?;
    let dir = root.join(".brainflow/runs");
    let mut out = Vec::new();
    if dir.exists() {
        for entry in std::fs::read_dir(dir).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            if entry.path().extension().and_then(|s| s.to_str()) == Some("json") {
                out.push(entry.file_name().to_string_lossy().to_string());
            }
        }
    }
    out.sort();
    Ok(out)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState {
            vault_root: Mutex::new(None),
        })
        .manage(sync_cmds::SyncState::default())
        .invoke_handler(tauri::generate_handler![
            greet,
            pick_vault,
            open_vault,
            create_vault_dialog,
            create_vault,
            list_vault_dir,
            list_notes,
            create_note,
            read_note,
            save_note,
            note_stat,
            analyze_note_cmd,
            note_links,
            vault_tags,
            search_vault,
            reindex_notes,
            knowledge_graph,
            list_note_snapshots,
            restore_note_snapshot,
            list_vault_templates,
            apply_note_template,
            open_daily_note,
            create_unique_note,
            random_note,
            list_bookmarks,
            toggle_bookmark,
            list_workspace_layouts,
            save_workspace_layout,
            load_workspace_layout,
            delete_workspace_layout,
            property_suggestions,
            set_note_property,
            ensure_foundations,
            rename_note,
            base_table,
            save_base_definition,
            list_canvases,
            read_canvas,
            write_canvas,
            import_dropped_text,
            llm_health,
            model_recommend,
            model_hardware,
            model_registry_status,
            model_set_secret,
            generate_workflow_slice,
            load_session,
            list_runs,
            sync_cmds::sync_status,
            sync_cmds::sync_auth_status,
            sync_cmds::sync_set_pat,
            sync_cmds::sync_logout,
            sync_cmds::sync_begin_device_flow,
            sync_cmds::sync_poll_device_flow,
            sync_cmds::sync_configure_clone,
            sync_cmds::sync_configure_create,
            sync_cmds::sync_run_now,
            sync_cmds::sync_on_change,
            sync_cmds::sync_resolve_conflicts,
            sync_cmds::sync_force_push_forbidden,
            sync_cmds::sync_is_ai_tool,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
