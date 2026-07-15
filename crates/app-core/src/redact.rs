//! Log and diagnostics redaction helpers.
//! Default: never emit secrets, raw prompts, or identifiable absolute paths.

use regex::Regex;
use std::sync::OnceLock;

fn secret_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"(?i)(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9\-._~+/]+=*)",
        )
        .expect("secret regex")
    })
}

fn windows_user_path_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?i)([A-Z]:\\Users\\)[^\\/\s]+").expect("win path regex")
    })
}

fn unix_user_path_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)(/home/)[^/\s]+").expect("unix path regex"))
}

fn prompt_like_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?is)(prompt|message|content)\s*[:=]\s*.{40,}").expect("prompt regex")
    })
}

/// Redact a single log line or diagnostic string for default (non-consented) logging.
pub fn redact_line(input: &str) -> String {
    let mut out = secret_re().replace_all(input, "<REDACTED_SECRET>").into_owned();
    out = windows_user_path_re()
        .replace_all(&out, "${1}<USER>")
        .into_owned();
    out = unix_user_path_re()
        .replace_all(&out, "${1}<USER>")
        .into_owned();
    out = prompt_like_re()
        .replace_all(&out, "$1=<REDACTED_CONTENT>")
        .into_owned();
    out
}

/// Prefer vault-relative paths in logs when a vault root is known.
pub fn redact_path(path: &str, vault_root: Option<&str>) -> String {
    if let Some(root) = vault_root {
        let root = root.trim_end_matches(['/', '\\']);
        if let Some(rest) = path.strip_prefix(root) {
            let rest = rest.trim_start_matches(['/', '\\']);
            return format!("vault:{rest}");
        }
    }
    redact_line(path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_github_pat() {
        let s = redact_line("token=ghp_abcdefghijklmnopqrstuvwxyz012345");
        assert!(s.contains("<REDACTED_SECRET>"));
        assert!(!s.contains("ghp_"));
    }

    #[test]
    fn redacts_windows_home() {
        let s = redact_line(r"open C:\Users\ericc\Documents\vault\note.md");
        assert!(s.contains(r"C:\Users\<USER>\"));
        assert!(!s.contains("ericc"));
    }

    #[test]
    fn vault_relative() {
        let s = redact_path(
            r"C:\data\myvault\notes\a.md",
            Some(r"C:\data\myvault"),
        );
        assert_eq!(s, "vault:notes\\a.md");
    }
}
