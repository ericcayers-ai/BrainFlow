//! Pre-commit scans: likely secrets and oversized / generated files.
//! Git LFS is documented as optional only — not auto-enabled here.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// Default warn threshold (10 MiB). LFS may help above this — see docs.
pub const LARGE_FILE_WARN_BYTES: u64 = 10 * 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PreflightKind {
    LikelySecret,
    LargeFile,
    GeneratedJunk,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PreflightWarning {
    pub path: String,
    pub kind: PreflightKind,
    pub detail: String,
}

/// Scan staged-like paths (vault-relative) for secrets and large files.
pub fn scan_paths(vault_root: &Path, relative_paths: &[String]) -> Vec<PreflightWarning> {
    let mut out = Vec::new();
    let secret_re = secret_patterns();
    for rel in relative_paths {
        let path = vault_root.join(rel);
        if !path.is_file() {
            continue;
        }
        if looks_like_generated(rel) {
            out.push(PreflightWarning {
                path: rel.clone(),
                kind: PreflightKind::GeneratedJunk,
                detail: "Looks like generated/cache junk; confirm before commit".into(),
            });
        }
        let mut file_len = 0u64;
        if let Ok(meta) = std::fs::metadata(&path) {
            file_len = meta.len();
            if file_len >= LARGE_FILE_WARN_BYTES {
                out.push(PreflightWarning {
                    path: rel.clone(),
                    kind: PreflightKind::LargeFile,
                    detail: format!(
                        "{file_len} bytes (≥ {LARGE_FILE_WARN_BYTES} warn threshold). Git LFS is optional — see docs/GITHUB_SYNC.md"
                    ),
                });
            }
        }
        // Only sniff small text-ish files for secrets.
        if file_len > 512 * 1024 {
            continue;
        }
        if let Ok(text) = std::fs::read_to_string(&path) {
            for (name, re) in &secret_re {
                if re.is_match(&text) {
                    out.push(PreflightWarning {
                        path: rel.clone(),
                        kind: PreflightKind::LikelySecret,
                        detail: format!("Matched pattern: {name}"),
                    });
                    break;
                }
            }
        }
    }
    out
}

fn looks_like_generated(rel: &str) -> bool {
    let lower = rel.to_lowercase();
    (lower.contains("onedrive") && lower.contains("conflict"))
        || lower.contains("-conflict.")
        || lower.ends_with(".sqlite")
        || lower.contains("/__pycache__/")
        || lower.contains("\\__pycache__\\")
        || lower.ends_with(".tmp")
}

fn secret_patterns() -> Vec<(&'static str, Regex)> {
    vec![
        (
            "github_pat",
            Regex::new(r"ghp_[A-Za-z0-9]{20,}").expect("regex"),
        ),
        (
            "github_fine_grained",
            Regex::new(r"github_pat_[A-Za-z0-9_]{20,}").expect("regex"),
        ),
        (
            "github_oauth",
            Regex::new(r"gho_[A-Za-z0-9]{20,}").expect("regex"),
        ),
        (
            "aws_akid",
            Regex::new(r"AKIA[0-9A-Z]{16}").expect("regex"),
        ),
        (
            "private_key_header",
            Regex::new(r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----").expect("regex"),
        ),
        (
            "slack_token",
            Regex::new(r"xox[baprs]-[0-9A-Za-z-]{10,}").expect("regex"),
        ),
        (
            "openai_sk",
            Regex::new(r"sk-[A-Za-z0-9]{20,}").expect("regex"),
        ),
    ]
}

/// Block commit when likely secrets are present (AC: secret scan blocks).
pub fn secrets_block_commit(warnings: &[PreflightWarning]) -> bool {
    warnings
        .iter()
        .any(|w| matches!(w.kind, PreflightKind::LikelySecret))
}

/// Large-file note used by UI consumers of preflight results.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LargeFileNote {
    pub path: PathBuf,
    pub bytes: u64,
}

fn parse_bytes_from_detail(detail: &str) -> Option<u64> {
    detail
        .split_whitespace()
        .next()
        .and_then(|s| s.parse::<u64>().ok())
}

pub fn large_file_notes(warnings: &[PreflightWarning]) -> Vec<LargeFileNote> {
    warnings
        .iter()
        .filter(|w| matches!(w.kind, PreflightKind::LargeFile))
        .map(|w| LargeFileNote {
            path: PathBuf::from(&w.path),
            bytes: parse_bytes_from_detail(&w.detail).unwrap_or(LARGE_FILE_WARN_BYTES),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn detects_pat() {
        let dir = tempdir().unwrap();
        let rel = "notes/leaky.md".to_string();
        std::fs::create_dir_all(dir.path().join("notes")).unwrap();
        std::fs::write(
            dir.path().join(&rel),
            "token ghp_abcdefghijklmnopqrstuvwxyz0123456789\n",
        )
        .unwrap();
        let w = scan_paths(dir.path(), &[rel]);
        assert!(secrets_block_commit(&w));
    }

    #[test]
    fn detects_private_key() {
        let dir = tempdir().unwrap();
        let rel = "keys/id.pem".to_string();
        std::fs::create_dir_all(dir.path().join("keys")).unwrap();
        std::fs::write(
            dir.path().join(&rel),
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n",
        )
        .unwrap();
        let w = scan_paths(dir.path(), &[rel]);
        assert!(secrets_block_commit(&w));
        assert!(w.iter().any(|x| x.detail.contains("private_key")));
    }

    #[test]
    fn detects_aws_akid() {
        let dir = tempdir().unwrap();
        let rel = "cfg.env".to_string();
        std::fs::write(dir.path().join(&rel), "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n").unwrap();
        let w = scan_paths(dir.path(), &[rel]);
        assert!(secrets_block_commit(&w));
    }

    #[test]
    fn warns_large_file_with_actual_size() {
        let dir = tempdir().unwrap();
        let rel = "blob.bin".to_string();
        // Use a smaller threshold via writing a file and checking LARGE_FILE path —
        // write exactly at threshold boundary by temporarily scanning after writing warn-sized content.
        // For unit speed we write a stub and inject via scan after creating a big-enough file may be slow;
        // instead assert large_file_notes parses detail bytes from a constructed warning.
        let fake = PreflightWarning {
            path: rel.clone(),
            kind: PreflightKind::LargeFile,
            detail: format!("12345678 bytes (≥ {LARGE_FILE_WARN_BYTES} warn threshold)."),
        };
        let notes = large_file_notes(&[fake]);
        assert_eq!(notes.len(), 1);
        assert_eq!(notes[0].bytes, 12_345_678);

        // Also exercise scan on a small generated oversize substitute: create file >= threshold is heavy;
        // create empty and manually verify GeneratedJunk for OneDrive conflict names.
        let junk = "Note-OneDrive-conflict.md".to_string();
        std::fs::write(dir.path().join(&junk), "x\n").unwrap();
        let w = scan_paths(dir.path(), &[junk]);
        assert!(w.iter().any(|x| matches!(x.kind, PreflightKind::GeneratedJunk)));
    }

    #[test]
    fn large_file_scan_over_threshold() {
        let dir = tempdir().unwrap();
        let rel = "big.bin".to_string();
        // Write slightly over threshold using sparse approach: set_len if available.
        let path = dir.path().join(&rel);
        let f = std::fs::File::create(&path).unwrap();
        f.set_len(LARGE_FILE_WARN_BYTES).unwrap();
        drop(f);
        let w = scan_paths(dir.path(), &[rel]);
        assert!(w.iter().any(|x| matches!(x.kind, PreflightKind::LargeFile)));
        let notes = large_file_notes(&w);
        assert_eq!(notes[0].bytes, LARGE_FILE_WARN_BYTES);
    }
}
