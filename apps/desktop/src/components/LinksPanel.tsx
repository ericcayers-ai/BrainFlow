import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

type LinkRef = {
  from_path: string;
  to_path?: string | null;
  to_target: string;
  raw: string;
};

type NoteLinks = {
  path: string;
  outgoing: LinkRef[];
  backlinks: LinkRef[];
  tags: string[];
  unresolved: { target: string; raw: string }[];
};

type PropertySuggestion = {
  key: string;
  count: number;
  sample_values: string[];
};

type Props = {
  vaultOpen: boolean;
  notePath: string;
  onOpenNote: (path: string) => void;
  onApplyProperty?: (key: string, value: string) => void;
  refreshKey: number;
};

export default function LinksPanel({
  vaultOpen,
  notePath,
  onOpenNote,
  onApplyProperty,
  refreshKey,
}: Props) {
  const [links, setLinks] = useState<NoteLinks | null>(null);
  const [graphSummary, setGraphSummary] = useState<string>("");
  const [suggestions, setSuggestions] = useState<PropertySuggestion[]>([]);

  useEffect(() => {
    if (!vaultOpen || !notePath) {
      setLinks(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await invoke<NoteLinks>("note_links", {
          relativePath: notePath,
        });
        if (!cancelled) setLinks(data);
        const local = await invoke<{
          nodes: unknown[];
          edges: unknown[];
          scope?: string;
        }>("knowledge_graph", {
          focusPath: notePath,
          localOnly: true,
        });
        if (!cancelled) {
          setGraphSummary(
            `Local graph: ${local.nodes?.length ?? 0} nodes · ${local.edges?.length ?? 0} edges`,
          );
        }
        const schema = await invoke<PropertySuggestion[]>("property_suggestions");
        if (!cancelled) setSuggestions(schema.slice(0, 12));
      } catch {
        if (!cancelled) setLinks(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [vaultOpen, notePath, refreshKey]);

  if (!vaultOpen) return null;

  return (
    <div className="links-panel">
      <h3>Properties & links</h3>
      {links ? (
        <>
          <p className="meta-line">
            Tags:{" "}
            {links.tags.length
              ? links.tags.map((t) => (
                  <span key={t} className="tag-chip">
                    #{t}
                  </span>
                ))
              : "—"}
          </p>
          <p className="meta-line muted-copy">{graphSummary}</p>
          <div className="link-block">
            <strong>Schema suggestions</strong>
            <ul className="schema-list">
              {suggestions.length === 0 ? (
                <li className="muted-copy">No properties yet</li>
              ) : (
                suggestions.map((s) => (
                  <li key={s.key}>
                    <button
                      type="button"
                      className="linkish"
                      title={
                        s.sample_values.length
                          ? `e.g. ${s.sample_values.slice(0, 3).join(", ")}`
                          : undefined
                      }
                      onClick={() =>
                        onApplyProperty?.(
                          s.key,
                          s.sample_values[0] ?? (s.key === "tags" ? "" : ""),
                        )
                      }
                    >
                      {s.key}
                    </button>
                    <span className="muted-copy"> ×{s.count}</span>
                  </li>
                ))
              )}
            </ul>
          </div>
          <div className="link-block">
            <strong>Backlinks</strong>
            <ul>
              {links.backlinks.length === 0 ? (
                <li className="muted-copy">None</li>
              ) : (
                links.backlinks.map((b) => (
                  <li key={`${b.from_path}-${b.raw}`}>
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => onOpenNote(b.from_path)}
                    >
                      {b.from_path}
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>
          <div className="link-block">
            <strong>Outgoing</strong>
            <ul>
              {links.outgoing.length === 0 ? (
                <li className="muted-copy">None</li>
              ) : (
                links.outgoing.map((o) => (
                  <li key={`${o.to_target}-${o.raw}`}>
                    {o.to_path ? (
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => onOpenNote(o.to_path!)}
                      >
                        {o.raw}
                      </button>
                    ) : (
                      <span className="unresolved" title="Unresolved">
                        {o.raw}
                      </span>
                    )}
                  </li>
                ))
              )}
            </ul>
          </div>
        </>
      ) : (
        <p className="muted-copy">Select a note.</p>
      )}
    </div>
  );
}
