//! Application-core helpers shared by the Tauri shell.
//! Worker IPC framing and vault session state live here so `src-tauri` stays thin.

pub mod redact;

use brainflow_vault::{self as vault, VaultInfo};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use thiserror::Error;

pub use brainflow_graph;
pub use brainflow_policy;
pub use brainflow_storage;
pub use brainflow_sync;
pub use brainflow_vault;

#[derive(Debug, Error)]
pub enum AppCoreError {
    #[error(transparent)]
    Vault(#[from] vault::VaultError),
    #[error("no vault open")]
    NoVault,
    #[error("{0}")]
    Message(String),
}

#[derive(Debug, Default)]
pub struct AppState {
    pub vault: Option<VaultInfo>,
    /// Absolute path to local catalog (OS app data), not inside the vault.
    pub catalog_path: Option<PathBuf>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenVaultResult {
    pub root: String,
    pub onedrive_warning: bool,
}

pub fn open_vault_session(state: &mut AppState, path: &str) -> Result<OpenVaultResult, AppCoreError> {
    let info = vault::open_vault(path)?;
    let result = OpenVaultResult {
        root: info.root.display().to_string(),
        onedrive_warning: info.onedrive_warning,
    };
    state.vault = Some(info);
    Ok(result)
}

pub fn require_vault(state: &AppState) -> Result<&VaultInfo, AppCoreError> {
    state.vault.as_ref().ok_or(AppCoreError::NoVault)
}

/// JSON-RPC framing for private stdio IPC with the Python worker.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: String,
    pub method: String,
    pub params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcErrorBody>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcErrorBody {
    pub code: i32,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<serde_json::Value>,
}

pub fn encode_rpc_line(value: &impl Serialize) -> Result<String, serde_json::Error> {
    let mut s = serde_json::to_string(value)?;
    s.push('\n');
    Ok(s)
}
