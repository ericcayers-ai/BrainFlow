import { useMemo, useState } from "react";

export type SlashCommand = {
  id: string;
  label: string;
  insert?: string;
  run?: () => void;
};

const DEFAULT_SLASH: SlashCommand[] = [
  { id: "h1", label: "Heading 1", insert: "# " },
  { id: "h2", label: "Heading 2", insert: "## " },
  { id: "h3", label: "Heading 3", insert: "### " },
  { id: "bullet", label: "Bullet list", insert: "- " },
  { id: "task", label: "Task", insert: "- [ ] " },
  { id: "callout", label: "Callout", insert: "> [!note] \n> " },
  { id: "table", label: "Table", insert: "| A | B |\n| --- | --- |\n|  |  |\n" },
  { id: "fn", label: "Footnote", insert: "[^1]\n\n[^1]: " },
  { id: "math", label: "Math block", insert: "$$\n\n$$\n" },
  { id: "code", label: "Code fence", insert: "```\n\n```\n" },
];

type Props = {
  open: boolean;
  query: string;
  extra?: SlashCommand[];
  onPick: (cmd: SlashCommand) => void;
  onClose: () => void;
};

export function filterSlashCommands(
  query: string,
  extra: SlashCommand[] = [],
): SlashCommand[] {
  const all = [...DEFAULT_SLASH, ...extra];
  const q = query.trim().toLowerCase();
  if (!q) return all;
  return all.filter(
    (c) =>
      c.label.toLowerCase().includes(q) || c.id.toLowerCase().includes(q),
  );
}

export default function SlashMenu({ open, query, extra = [], onPick, onClose }: Props) {
  const items = useMemo(() => filterSlashCommands(query, extra), [query, extra]);
  const [active, setActive] = useState(0);

  if (!open) return null;

  return (
    <div className="slash-menu" role="listbox" aria-label="Slash commands">
      {items.length === 0 ? (
        <div className="slash-empty muted-copy">No matches</div>
      ) : (
        items.map((cmd, i) => (
          <button
            key={cmd.id}
            type="button"
            role="option"
            aria-selected={i === active}
            className={`slash-item${i === active ? " active" : ""}`}
            onMouseEnter={() => setActive(i)}
            onClick={() => {
              onPick(cmd);
              onClose();
            }}
          >
            <span>{cmd.label}</span>
            <code>{cmd.id}</code>
          </button>
        ))
      )}
    </div>
  );
}

export { DEFAULT_SLASH };
