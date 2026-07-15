import { useCallback, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

export type BaseRow = {
  path: string;
  title: string;
  tags: string[];
  aliases: string[];
  updated_at?: number | null;
  size?: number | null;
  fields?: [string, string][];
  formula_values?: [string, string][];
};

type BaseDefinition = {
  title?: string;
  columns?: string[];
  formulas?: Record<string, string>;
  schema_version?: number;
  kind?: string;
  id?: string;
  source?: string;
  filters?: unknown[];
  sort?: unknown[];
};

type Props = {
  vaultOpen: boolean;
  onOpenNote: (path: string) => void;
  onNoteMutated?: (path: string, content: string) => void;
  refreshKey: number;
};

export default function BasesPanel({
  vaultOpen,
  onOpenNote,
  onNoteMutated,
  refreshKey,
}: Props) {
  const [rows, setRows] = useState<BaseRow[]>([]);
  const [definition, setDefinition] = useState<BaseDefinition | null>(null);
  const [title, setTitle] = useState("Notes");
  const [filter, setFilter] = useState("");
  const [sortColumn, setSortColumn] = useState("path");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [formulaName, setFormulaName] = useState("tag_count");
  const [formulaExpr, setFormulaExpr] = useState("len(tags)");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<{
    path: string;
    column: "title" | "tags";
    value: string;
  } | null>(null);

  const formulaColumns = useMemo(() => {
    const keys = Object.keys(definition?.formulas ?? {});
    return keys;
  }, [definition]);

  const load = useCallback(async () => {
    if (!vaultOpen) {
      setRows([]);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await invoke<{
        definition: BaseDefinition;
        rows: BaseRow[];
      }>("base_table", {
        basePath: null,
        filterColumn: filter.trim() ? "tags" : null,
        filterValue: filter.trim() || null,
        sortColumn,
        sortDirection: sortDir,
      });
      setDefinition(res.definition ?? null);
      setTitle(res.definition?.title ?? "Notes");
      setRows(res.rows ?? []);
    } catch (e) {
      setError(String(e));
      setRows([]);
    } finally {
      setBusy(false);
    }
  }, [vaultOpen, filter, sortColumn, sortDir]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  function toggleSort(col: string) {
    if (sortColumn === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(col);
      setSortDir("asc");
    }
  }

  async function saveFormula() {
    if (!vaultOpen || !formulaName.trim()) return;
    setBusy(true);
    try {
      const def: BaseDefinition = {
        schema_version: definition?.schema_version ?? 1,
        kind: definition?.kind ?? "base",
        id: definition?.id ?? "notes",
        title: definition?.title ?? "Notes",
        source: definition?.source ?? "vault_notes",
        columns: definition?.columns ?? ["path", "title", "tags", "updated_at"],
        filters: definition?.filters ?? [],
        sort: definition?.sort ?? [],
        formulas: {
          ...(definition?.formulas ?? {}),
          [formulaName.trim()]: formulaExpr.trim(),
        },
      };
      await invoke("save_base_definition", {
        relativePath: ".brainflow/bases/notes.base.json",
        definition: def,
      });
      setDefinition(def);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function commitEdit() {
    if (!editing) return;
    setBusy(true);
    try {
      const key = editing.column === "title" ? "title" : "tags";
      // title is stored as first heading normally; for bases we edit tags / a title field.
      const propKey = editing.column === "tags" ? "tags" : "title";
      const content = await invoke<string>("set_note_property", {
        relativePath: editing.path,
        key: propKey,
        value: editing.value,
      });
      onNoteMutated?.(editing.path, content);
      setEditing(null);
      await load();
      void key;
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function formulaCell(row: BaseRow, col: string): string {
    const hit = (row.formula_values ?? []).find(([k]) => k === col);
    return hit?.[1] ?? "";
  }

  if (!vaultOpen) {
    return <p className="muted-copy">Open a vault to browse the Notes base.</p>;
  }

  return (
    <div className="bases-panel" aria-label="Bases table">
      <div className="bases-toolbar">
        <h3>{title}</h3>
        <label className="field inline">
          <span>Filter tags</span>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="contains…"
          />
        </label>
        <button type="button" className="ghost" onClick={() => void load()} disabled={busy}>
          Refresh
        </button>
      </div>

      <div className="bases-formula-bar">
        <label className="field inline">
          <span>Formula name</span>
          <input value={formulaName} onChange={(e) => setFormulaName(e.target.value)} />
        </label>
        <label className="field inline grow">
          <span>Expression</span>
          <input
            value={formulaExpr}
            onChange={(e) => setFormulaExpr(e.target.value)}
            placeholder='len(tags) · word_count · contains(tags,"x")'
          />
        </label>
        <button type="button" onClick={() => void saveFormula()} disabled={busy}>
          Add formula
        </button>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="bases-table-wrap">
        <table className="bases-table">
          <thead>
            <tr>
              {(["path", "title", "tags", "updated_at"] as const).map((col) => (
                <th key={col}>
                  <button type="button" className="th-sort" onClick={() => toggleSort(col)}>
                    {col}
                    {sortColumn === col ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                  </button>
                </th>
              ))}
              {formulaColumns.map((col) => (
                <th key={col}>
                  <button type="button" className="th-sort" onClick={() => toggleSort(col)}>
                    {col}ƒ
                    {sortColumn === col ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.path}>
                <td>
                  <button
                    type="button"
                    className="linkish"
                    onClick={() => onOpenNote(r.path)}
                  >
                    {r.path}
                  </button>
                </td>
                <td
                  className="editable-cell"
                  onDoubleClick={() =>
                    setEditing({ path: r.path, column: "title", value: r.title })
                  }
                  title="Double-click to edit title property"
                >
                  {editing?.path === r.path && editing.column === "title" ? (
                    <input
                      autoFocus
                      value={editing.value}
                      onChange={(e) =>
                        setEditing({ ...editing, value: e.target.value })
                      }
                      onBlur={() => void commitEdit()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void commitEdit();
                        if (e.key === "Escape") setEditing(null);
                      }}
                    />
                  ) : (
                    r.title
                  )}
                </td>
                <td
                  className="editable-cell"
                  onDoubleClick={() =>
                    setEditing({
                      path: r.path,
                      column: "tags",
                      value: (r.tags ?? []).join(", "),
                    })
                  }
                  title="Double-click to edit tags"
                >
                  {editing?.path === r.path && editing.column === "tags" ? (
                    <input
                      autoFocus
                      value={editing.value}
                      onChange={(e) =>
                        setEditing({ ...editing, value: e.target.value })
                      }
                      onBlur={() => void commitEdit()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void commitEdit();
                        if (e.key === "Escape") setEditing(null);
                      }}
                    />
                  ) : (
                    (r.tags ?? []).join(", ")
                  )}
                </td>
                <td>
                  {r.updated_at
                    ? new Date(r.updated_at).toLocaleString()
                    : "—"}
                </td>
                {formulaColumns.map((col) => (
                  <td key={col}>{formulaCell(r, col)}</td>
                ))}
              </tr>
            ))}
            {!rows.length && !busy ? (
              <tr>
                <td colSpan={4 + formulaColumns.length} className="muted-copy">
                  No rows match.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
