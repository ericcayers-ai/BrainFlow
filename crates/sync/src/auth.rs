//! GitHub authentication: PAT and OAuth device flow.
//! Tokens are stored only via [`crate::credentials`] (OS keychain).

use crate::credentials::{self, AuthMethod, CredentialError, StoredAuthMeta};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AuthError {
    #[error(transparent)]
    Credential(#[from] CredentialError),
    #[error("http: {0}")]
    Http(String),
    #[error("device flow: {0}")]
    DeviceFlow(String),
    #[error("github api: {0}")]
    Api(String),
    #[error("missing client id — set BRAINFLOW_GITHUB_CLIENT_ID for device flow")]
    MissingClientId,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceCodeResponse {
    pub device_code: String,
    pub user_code: String,
    pub verification_uri: String,
    pub expires_in: u64,
    pub interval: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthStatus {
    pub authenticated: bool,
    pub method: Option<AuthMethod>,
    pub login: Option<String>,
    pub token_hint: Option<String>,
}

/// Persist a personal access token (classic or fine-grained) in the OS store.
pub fn set_personal_access_token(token: &str, login: Option<String>) -> Result<AuthStatus, AuthError> {
    let token = token.trim();
    if token.is_empty() {
        return Err(AuthError::Api("empty token".into()));
    }
    credentials::store_token(token)?;
    let meta = StoredAuthMeta {
        method: AuthMethod::PersonalAccessToken,
        login: login.clone(),
        scopes_hint: "repo (private vault sync)".into(),
    };
    // Meta is non-secret; store beside vault local sync journal optional — keep in-memory via return.
    let _ = meta;
    Ok(AuthStatus {
        authenticated: true,
        method: Some(AuthMethod::PersonalAccessToken),
        login,
        token_hint: Some(credentials::redact_token(token)),
    })
}

pub fn auth_status() -> AuthStatus {
    match credentials::load_token() {
        Ok(token) => AuthStatus {
            authenticated: true,
            method: Some(AuthMethod::PersonalAccessToken),
            login: None,
            token_hint: Some(credentials::redact_token(&token)),
        },
        Err(_) => AuthStatus {
            authenticated: false,
            method: None,
            login: None,
            token_hint: None,
        },
    }
}

pub fn logout() -> Result<(), AuthError> {
    credentials::clear_token()?;
    Ok(())
}

/// Start GitHub OAuth device flow. Requires `BRAINFLOW_GITHUB_CLIENT_ID`.
pub fn begin_device_flow() -> Result<DeviceCodeResponse, AuthError> {
    let client_id = std::env::var("BRAINFLOW_GITHUB_CLIENT_ID")
        .map_err(|_| AuthError::MissingClientId)?;
    let body = ureq::post("https://github.com/login/device/code")
        .set("Accept", "application/json")
        .send_form(&[
            ("client_id", client_id.as_str()),
            ("scope", "repo"),
        ])
        .map_err(|e| AuthError::Http(e.to_string()))?;
    body.into_json::<DeviceCodeResponse>()
        .map_err(|e| AuthError::Http(e.to_string()))
}

#[derive(Debug, Deserialize)]
struct TokenPollResponse {
    access_token: Option<String>,
    error: Option<String>,
    error_description: Option<String>,
}

/// Poll until the user completes device authorization (or failure).
pub fn poll_device_flow(device_code: &str, interval_secs: u64) -> Result<AuthStatus, AuthError> {
    let client_id = std::env::var("BRAINFLOW_GITHUB_CLIENT_ID")
        .map_err(|_| AuthError::MissingClientId)?;
    let max_attempts = 120u32;
    for _ in 0..max_attempts {
        std::thread::sleep(std::time::Duration::from_secs(interval_secs.max(1)));
        let body = ureq::post("https://github.com/login/oauth/access_token")
            .set("Accept", "application/json")
            .send_form(&[
                ("client_id", client_id.as_str()),
                ("device_code", device_code),
                ("grant_type", "urn:ietf:params:oauth:grant-type:device_code"),
            ])
            .map_err(|e| AuthError::Http(e.to_string()))?;
        let parsed: TokenPollResponse = body
            .into_json()
            .map_err(|e| AuthError::Http(e.to_string()))?;
        if let Some(token) = parsed.access_token {
            credentials::store_token(&token)?;
            let login = fetch_login(&token).ok();
            return Ok(AuthStatus {
                authenticated: true,
                method: Some(AuthMethod::DeviceFlow),
                login,
                token_hint: Some(credentials::redact_token(&token)),
            });
        }
        match parsed.error.as_deref() {
            Some("authorization_pending") | Some("slow_down") => continue,
            Some(other) => {
                return Err(AuthError::DeviceFlow(
                    parsed
                        .error_description
                        .unwrap_or_else(|| other.to_string()),
                ));
            }
            None => continue,
        }
    }
    Err(AuthError::DeviceFlow("timed out waiting for authorization".into()))
}

pub fn fetch_login(token: &str) -> Result<String, AuthError> {
    let resp = ureq::get("https://api.github.com/user")
        .set("Authorization", &format!("Bearer {token}"))
        .set("User-Agent", "BrainFlow-Sync")
        .set("Accept", "application/vnd.github+json")
        .call()
        .map_err(|e| AuthError::Http(e.to_string()))?;
    let v: serde_json::Value = resp
        .into_json()
        .map_err(|e| AuthError::Http(e.to_string()))?;
    v.get("login")
        .and_then(|x| x.as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| AuthError::Api("no login in /user".into()))
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateRepoRequest {
    pub name: String,
    pub private: bool,
    pub description: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RemoteRepo {
    pub full_name: String,
    pub clone_url: String,
    pub html_url: String,
    pub private: bool,
}

/// Create a GitHub repository (default private) using the stored token.
pub fn create_repository(req: &CreateRepoRequest) -> Result<RemoteRepo, AuthError> {
    let token = credentials::load_token()?;
    let mut body = serde_json::json!({
        "name": req.name,
        "private": req.private,
        "auto_init": false,
    });
    if let Some(desc) = &req.description {
        body["description"] = serde_json::json!(desc);
    }
    let resp = ureq::post("https://api.github.com/user/repos")
        .set("Authorization", &format!("Bearer {token}"))
        .set("User-Agent", "BrainFlow-Sync")
        .set("Accept", "application/vnd.github+json")
        .send_json(body)
        .map_err(|e| AuthError::Http(e.to_string()))?;
    if !(200..300).contains(&resp.status()) {
        let status = resp.status();
        let text = resp.into_string().unwrap_or_default();
        return Err(AuthError::Api(format!("HTTP {status}: {text}")));
    }
    let v: serde_json::Value = resp
        .into_json()
        .map_err(|e| AuthError::Http(e.to_string()))?;
    Ok(RemoteRepo {
        full_name: v
            .get("full_name")
            .and_then(|x| x.as_str())
            .unwrap_or_default()
            .into(),
        clone_url: v
            .get("clone_url")
            .and_then(|x| x.as_str())
            .unwrap_or_default()
            .into(),
        html_url: v
            .get("html_url")
            .and_then(|x| x.as_str())
            .unwrap_or_default()
            .into(),
        private: v
            .get("private")
            .and_then(|x| x.as_bool())
            .unwrap_or(true),
    })
}
