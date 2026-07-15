import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

export type VaultEntry = {
  relative_path: string;
  name: string;
  kind: "dir" | "note" | "file";
  children?: VaultEntry[] | null;
};

type Props = {
  vaultOpen: boolean;
  activePath: string;
  onOpenNote: (path: string) => void;
  refreshKey: number;
};

function TreeNode({
  entry,
  depth,
  activePath,
  onOpenNote,
  vaultOpen,
}: {
  entry: VaultEntry;
  depth: number;
  activePath: string;
  onOpenNote: (path: string) => void;
  vaultOpen: boolean;
}) {
  const [open, setOpen] = useState(depth < 1);
  const [children, setChildren] = useState<VaultEntry[] | null>(null);

  useEffect(() => {
    if (!vaultOpen || entry.kind !== "dir" || !open) return;
    let cancelled = false;
    (async () => {
      try {
        const list = await invoke<VaultEntry[]>("list_vault_dir", {
          relativePath: entry.relative_path,
        });
        if (!cancelled) setChildren(list);
      } catch {
        if (!cancelled) setChildren([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [vaultOpen, entry.kind, entry.relative_path, open]);

  if (entry.kind === "dir") {
    return (
      <div className="tree-node">
        <button
          type="button"
          className="tree-row"
          style={{ paddingLeft: `${0.35 + depth * 0.75}rem` }}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="tree-twist" aria-hidden>
            {open ? "▾" : "▸"}
          </span>
          <span className="tree-label">{entry.name}</span>
        </button>
        {open && children
          ? children.map((c) => (
              <TreeNode
                key={c.relative_path}
                entry={c}
                depth={depth + 1}
                activePath={activePath}
                onOpenNote={onOpenNote}
                vaultOpen={vaultOpen}
              />
            ))
          : null}
      </div>
    );
  }

  if (entry.kind !== "note") {
    return (
      <div
        className="tree-row muted"
        style={{ paddingLeft: `${0.35 + depth * 0.75}rem` }}
        title={entry.relative_path}
      >
        {entry.name}
      </div>
    );
  }

  const active = entry.relative_path === activePath;
  return (
    <button
      type="button"
      className={`tree-row note${active ? " active" : ""}`}
      style={{ paddingLeft: `${0.35 + depth * 0.75}rem` }}
      onClick={() => onOpenNote(entry.relative_path)}
      title={entry.relative_path}
    >
      <span className="tree-label">{entry.name}</span>
    </button>
  );
}

export default function FileExplorer({
  vaultOpen,
  activePath,
  onOpenNote,
  refreshKey,
}: Props) {
  const [roots, setRoots] = useState<VaultEntry[]>([]);

  useEffect(() => {
    if (!vaultOpen) {
      setRoots([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const list = await invoke<VaultEntry[]>("list_vault_dir", {
          relativePath: "",
        });
        if (!cancelled) setRoots(list);
      } catch {
        if (!cancelled) setRoots([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [vaultOpen, refreshKey]);

  if (!vaultOpen) {
    return <p className="muted-copy">Open or create a vault to browse notes.</p>;
  }

  return (
    <div className="explorer" role="tree" aria-label="Vault files">
      {roots.map((e) => (
        <TreeNode
          key={`${e.relative_path}-${refreshKey}`}
          entry={e}
          depth={0}
          activePath={activePath}
          onOpenNote={onOpenNote}
          vaultOpen={vaultOpen}
        />
      ))}
    </div>
  );
}
