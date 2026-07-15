//! OS credential store for GitHub tokens — never the vault.

use keyring::Entry;
use serde::{Deserialize, Serialize};
use thiserror::Error;

const SERVICE: &str = "BrainFlow";
const ACCOUNT_GITHUB: &str = "github-token";

#[derive(Debug, Error)]
pub enum CredentialError {
    #[error("credential store: {0}")]
    Keyring(String),
    #[error("no GitHub token stored")]
    Missing,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredAuthMeta {
    /// How the token was obtained.
    pub method: AuthMethod,
    /// GitHub login if known.
    pub login: Option<String>,
    pub scopes_hint: String,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AuthMethod {
    /// Classic / fine-grained PAT pasted by the user.
    PersonalAccessToken,
    /// OAuth device authorization grant.
    DeviceFlow,
    /// GitHub App installation token (user configured).
    GitHubApp,
}

pub fn store_token(token: &str) -> Result<(), CredentialError> {
    let entry = Entry::new(SERVICE, ACCOUNT_GITHUB)
        .map_err(|e| CredentialError::Keyring(e.to_string()))?;
    entry
        .set_password(token)
        .map_err(|e| CredentialError::Keyring(e.to_string()))?;
    Ok(())
}

pub fn load_token() -> Result<String, CredentialError> {
    let entry = Entry::new(SERVICE, ACCOUNT_GITHUB)
        .map_err(|e| CredentialError::Keyring(e.to_string()))?;
    entry.get_password().map_err(|e| match e {
        keyring::Error::NoEntry => CredentialError::Missing,
        other => CredentialError::Keyring(other.to_string()),
    })
}

pub fn clear_token() -> Result<(), CredentialError> {
    let entry = Entry::new(SERVICE, ACCOUNT_GITHUB)
        .map_err(|e| CredentialError::Keyring(e.to_string()))?;
    match entry.delete_credential() {
        Ok(()) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(CredentialError::Keyring(e.to_string())),
    }
}

pub fn has_token() -> bool {
    load_token().is_ok()
}

/// Redact a token for logs/UI (never log full credentials).
pub fn redact_token(token: &str) -> String {
    if token.len() <= 8 {
        return "****".into();
    }
    format!("{}…{}", &token[..4], &token[token.len() - 4..])
}
