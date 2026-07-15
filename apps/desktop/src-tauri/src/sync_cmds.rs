//! Tauri commands for GitHub sync.
//! Sync is never exposed to the AI worker / LLM tools.

use brainflow_app_core::redact::redact_line;
use brainflow_sync::{
    auth_status, begin_device_flow, logout, poll_device_flow, set_personal_access_token,
    ConflictResolution, DeviceCodeResponse, SyncEngine, SyncStatus,
};
use serde::Serialize;
use std::path::PathBuf;
use std::sync::Mutex;

pub struct SyncState {
    pub engine: Mutex<Option<SyncEngine>>,
}

impl Default for SyncState {
    fn default() -> Self {
        Self {
            engine: Mutex::new(None),
        }
    }
}

fn rerr(e: impl std::fmt::Display) -> String {
    let msg = redact_line(&e.to_string());
    eprintln!("[brainflow:sync] {msg}");
    msg
}

fn with_engine<T>(
    state: &SyncState,
    f: impl FnOnce(&mut SyncEngine) -> Result<T, String>,
) -> Result<T, String> {
    let mut guard = state.engine.lock().map_err(rerr)?;
    let eng = guard
        .as_mut()
        .ok_or_else(|| "No vault sync engine — open a vault first".to_string())?;
    f(eng)
}

pub fn attach_vault(state: &SyncState, vault: &PathBuf) -> Result<SyncStatus, String> {
    let eng = SyncEngine::open(vault.clone()).map_err(rerr)?;
    let status = eng.status();
    *state.engine.lock().map_err(rerr)? = Some(eng);
    Ok(status)
}

#[tauri::command]
pub fn sync_status(state: tauri::State<'_, SyncState>) -> Result<SyncStatus, String> {
    with_engine(&state, |eng| Ok(eng.status()))
}

#[tauri::command]
pub fn sync_auth_status() -> brainflow_sync::AuthStatus {
    auth_status()
}

#[tauri::command]
pub fn sync_set_pat(token: String, login: Option<String>) -> Result<brainflow_sync::AuthStatus, String> {
    // Never log the raw token — redact_line covers PAT patterns if errors include it.
    set_personal_access_token(&token, login).map_err(rerr)
}

#[tauri::command]
pub fn sync_logout() -> Result<(), String> {
    logout().map_err(rerr)
}

#[tauri::command]
pub fn sync_begin_device_flow() -> Result<DeviceCodeResponse, String> {
    begin_device_flow().map_err(rerr)
}

#[tauri::command]
pub fn sync_poll_device_flow(device_code: String, interval_secs: u64) -> Result<brainflow_sync::AuthStatus, String> {
    poll_device_flow(&device_code, interval_secs).map_err(rerr)
}

#[derive(Debug, Serialize)]
pub struct ConfigureResult {
    pub status: SyncStatus,
    pub remote: Option<brainflow_sync::RemoteRepo>,
}

#[tauri::command]
pub fn sync_configure_clone(
    state: tauri::State<'_, SyncState>,
    url: String,
) -> Result<SyncStatus, String> {
    with_engine(&state, |eng| {
        eng.configure_clone(&url).map_err(rerr)?;
        Ok(eng.status())
    })
}

#[tauri::command]
pub fn sync_configure_create(
    state: tauri::State<'_, SyncState>,
    name: String,
) -> Result<ConfigureResult, String> {
    with_engine(&state, |eng| {
        let remote = eng.configure_create_private(&name).map_err(rerr)?;
        Ok(ConfigureResult {
            status: eng.status(),
            remote: Some(remote),
        })
    })
}

#[tauri::command]
pub fn sync_run_now(
    state: tauri::State<'_, SyncState>,
    offline: Option<bool>,
) -> Result<SyncStatus, String> {
    with_engine(&state, |eng| {
        // Treat network failure soft — status still returned.
        if let Err(e) = eng.run_cycle(offline.unwrap_or(false)) {
            let _ = rerr(e);
        }
        Ok(eng.status())
    })
}

#[tauri::command]
pub fn sync_on_change(state: tauri::State<'_, SyncState>) -> Result<SyncStatus, String> {
    with_engine(&state, |eng| {
        eng.on_fs_change();
        let _ = eng.tick();
        Ok(eng.status())
    })
}

#[tauri::command]
pub fn sync_resolve_conflicts(
    state: tauri::State<'_, SyncState>,
    resolutions: Vec<ConflictResolution>,
) -> Result<SyncStatus, String> {
    with_engine(&state, |eng| {
        eng.resolve_conflicts(resolutions).map_err(rerr)?;
        Ok(eng.status())
    })
}

#[tauri::command]
pub fn sync_force_push_forbidden() -> bool {
    brainflow_sync::force_push_forbidden()
}

#[tauri::command]
pub fn sync_is_ai_tool() -> bool {
    brainflow_sync::is_ai_tool()
}
