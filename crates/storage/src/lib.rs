//! Local rebuildable SQLite catalog with FTS5.
//! Indexes belong in OS app data — never inside OneDrive-synced vault roots.

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use std::path::Path;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum StorageError {
    #[error("sqlite: {0}")]
    Sqlite(#[from] rusqlite::Error),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchHit {
    pub path: String,
    pub snippet: Option<String>,
}

pub fn open_catalog(db_path: &Path) -> Result<Connection, StorageError> {
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let conn = Connection::open(db_path)?;
    conn.execute_batch(
        r#"
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS notes_meta (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            content_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            title TEXT,
            tags TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            path UNINDEXED,
            body,
            tags,
            title,
            tokenize = 'porter'
        );
        "#,
    )?;
    // Migrations for older foundation DBs that lack tags/title columns.
    let _ = conn.execute("ALTER TABLE notes_meta ADD COLUMN title TEXT", []);
    let _ = conn.execute("ALTER TABLE notes_meta ADD COLUMN tags TEXT", []);
    Ok(conn)
}

fn fts_has_extra_columns(conn: &Connection) -> bool {
    conn.prepare("SELECT title, tags FROM notes_fts LIMIT 0")
        .is_ok()
}

pub fn upsert_note(
    conn: &Connection,
    id: &str,
    path: &str,
    content_hash: &str,
    updated_at: &str,
    body: &str,
) -> Result<(), StorageError> {
    upsert_note_enriched(conn, id, path, content_hash, updated_at, body, "", "")
}

pub fn upsert_note_enriched(
    conn: &Connection,
    id: &str,
    path: &str,
    content_hash: &str,
    updated_at: &str,
    body: &str,
    title: &str,
    tags: &str,
) -> Result<(), StorageError> {
    // Stable id per path: reuse existing row id when present.
    let existing: Option<String> = conn
        .query_row(
            "SELECT id FROM notes_meta WHERE path = ?1",
            params![path],
            |row| row.get(0),
        )
        .optional()?;
    let id = existing.as_deref().unwrap_or(id);

    conn.execute(
        "INSERT INTO notes_meta(id, path, content_hash, updated_at, title, tags)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)
         ON CONFLICT(path) DO UPDATE SET
           content_hash=excluded.content_hash,
           updated_at=excluded.updated_at,
           title=excluded.title,
           tags=excluded.tags",
        params![id, path, content_hash, updated_at, title, tags],
    )?;
    // Keep a single FTS row per path.
    conn.execute("DELETE FROM notes_fts WHERE path = ?1", params![path])?;
    if fts_has_extra_columns(conn) {
        conn.execute(
            "INSERT INTO notes_fts(path, body, tags, title) VALUES (?1, ?2, ?3, ?4)",
            params![path, body, tags, title],
        )?;
    } else {
        conn.execute(
            "INSERT INTO notes_fts(path, body) VALUES (?1, ?2)",
            params![path, body],
        )?;
    }
    Ok(())
}

pub fn search_notes(conn: &Connection, query: &str) -> Result<Vec<String>, StorageError> {
    Ok(search_notes_detailed(conn, query)?
        .into_iter()
        .map(|h| h.path)
        .collect())
}

/// FTS search. Supports `tag:foo` prefix as a tags-column MATCH preference.
pub fn search_notes_detailed(conn: &Connection, query: &str) -> Result<Vec<SearchHit>, StorageError> {
    let q = query.trim();
    if q.is_empty() {
        return Ok(Vec::new());
    }

    if let Some(tag) = q.strip_prefix("tag:") {
        let tag = tag.trim();
        if tag.is_empty() {
            return Ok(Vec::new());
        }
        let like = format!("%{tag}%");
        let mut stmt = conn.prepare(
            "SELECT path FROM notes_meta WHERE lower(COALESCE(tags,'')) LIKE lower(?1) LIMIT 50",
        )?;
        let rows = stmt.query_map(params![like], |row| {
            Ok(SearchHit {
                path: row.get(0)?,
                snippet: None,
            })
        })?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        return Ok(out);
    }

    // Escape FTS special chars lightly by quoting phrases with spaces.
    let match_q = if q.contains(' ') && !q.contains('"') {
        format!("\"{q}\"")
    } else {
        q.to_string()
    };

    if fts_has_extra_columns(conn) {
        let mut stmt = conn.prepare(
            "SELECT path, snippet(notes_fts, 1, '[', ']', '…', 12)
             FROM notes_fts WHERE notes_fts MATCH ?1 LIMIT 50",
        )?;
        let rows = stmt.query_map(params![match_q], |row| {
            Ok(SearchHit {
                path: row.get(0)?,
                snippet: row.get(1)?,
            })
        })?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    } else {
        let mut stmt =
            conn.prepare("SELECT path FROM notes_fts WHERE notes_fts MATCH ?1 LIMIT 50")?;
        let rows = stmt.query_map(params![match_q], |row| {
            Ok(SearchHit {
                path: row.get(0)?,
                snippet: None,
            })
        })?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    }
}

pub fn list_indexed_paths(conn: &Connection) -> Result<Vec<String>, StorageError> {
    let mut stmt = conn.prepare("SELECT path FROM notes_meta ORDER BY path")?;
    let rows = stmt.query_map([], |row| row.get(0))?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r?);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn fts_roundtrip() {
        let dir = tempdir().unwrap();
        let db = dir.path().join("index.sqlite");
        let conn = open_catalog(&db).unwrap();
        upsert_note_enriched(
            &conn,
            "n1",
            "notes/a.md",
            "sha256:abc",
            "2026-07-15T00:00:00Z",
            "brainflow workflow graph layout",
            "A",
            "study,plan",
        )
        .unwrap();
        let hits = search_notes(&conn, "workflow").unwrap();
        assert_eq!(hits, vec!["notes/a.md".to_string()]);
        let tag_hits = search_notes_detailed(&conn, "tag:study").unwrap();
        assert_eq!(tag_hits[0].path, "notes/a.md");
    }

    #[test]
    fn upsert_keeps_stable_path_identity() {
        let dir = tempdir().unwrap();
        let db = dir.path().join("index.sqlite");
        let conn = open_catalog(&db).unwrap();
        upsert_note(&conn, "n1", "notes/a.md", "h1", "t1", "one").unwrap();
        upsert_note(&conn, "n2", "notes/a.md", "h2", "t2", "two").unwrap();
        let paths = list_indexed_paths(&conn).unwrap();
        assert_eq!(paths.len(), 1);
    }
}
