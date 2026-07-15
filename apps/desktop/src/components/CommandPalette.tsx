import { useEffect, useMemo, useState } from "react";

export type PaletteCommand = {
  id: string;
  label: string;
  hint?: string;
  run: () => void | Promise<void>;
};

type Props = {
  open: boolean;
  mode: "command" | "switcher" | "search";
  commands: PaletteCommand[];
  notes: { path: string; name: string }[];
  searchHits: { path: string; snippet?: string | null }[];
  onClose: () => void;
  onOpenNote: (path: string) => void;
  onSearch: (query: string) => void;
};

export default function CommandPalette({
  open,
  mode,
  commands,
  notes,
  searchHits,
  onClose,
  onOpenNote,
  onSearch,
}: Props) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (open) {
      setQuery("");
      setIndex(0);
    }
  }, [open, mode]);

  useEffect(() => {
    if (mode === "search") onSearch(query);
  }, [query, mode, onSearch]);

  const filteredCommands = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || c.id.toLowerCase().includes(q),
    );
  }, [commands, query]);

  const filteredNotes = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return notes.slice(0, 40);
    return notes
      .filter(
        (n) =>
          n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q),
      )
      .slice(0, 40);
  }, [notes, query]);

  const items =
    mode === "command"
      ? filteredCommands.map((c) => ({
          key: c.id,
          primary: c.label,
          secondary: c.hint,
          activate: () => void c.run(),
        }))
      : mode === "switcher"
        ? filteredNotes.map((n) => ({
            key: n.path,
            primary: n.name,
            secondary: n.path,
            activate: () => onOpenNote(n.path),
          }))
        : searchHits.map((h) => ({
            key: h.path,
            primary: h.path,
            secondary: h.snippet ?? undefined,
            activate: () => onOpenNote(h.path),
          }));

  useEffect(() => {
    setIndex(0);
  }, [query, mode]);

  if (!open) return null;

  const title =
    mode === "command"
      ? "Command palette"
      : mode === "switcher"
        ? "Quick switcher"
        : "Search vault";

  return (
    <div
      className="palette-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            onClose();
          } else if (e.key === "ArrowDown") {
            e.preventDefault();
            setIndex((i) => Math.min(i + 1, Math.max(items.length - 1, 0)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setIndex((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter" && items[index]) {
            e.preventDefault();
            items[index].activate();
            onClose();
          }
        }}
      >
        <div className="palette-title">{title}</div>
        <input
          autoFocus
          className="palette-input"
          value={query}
          placeholder={
            mode === "search"
              ? "FTS query — use tag:name for tags"
              : mode === "switcher"
                ? "Jump to note…"
                : "Run a command…"
          }
          onChange={(e) => setQuery(e.target.value)}
        />
        <ul className="palette-list">
          {items.length === 0 ? (
            <li className="palette-empty">No matches</li>
          ) : (
            items.map((item, i) => (
              <li key={item.key}>
                <button
                  type="button"
                  className={`palette-item${i === index ? " active" : ""}`}
                  onMouseEnter={() => setIndex(i)}
                  onClick={() => {
                    item.activate();
                    onClose();
                  }}
                >
                  <span>{item.primary}</span>
                  {item.secondary ? (
                    <span className="palette-secondary">{item.secondary}</span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
