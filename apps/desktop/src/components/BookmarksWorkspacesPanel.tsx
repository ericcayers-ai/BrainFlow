import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

export type BookmarkItem = {
  path: string;
  title: string;
  pinned?: boolean;
};

export type WorkspaceListItem = {
  id: string;
  title: string;
  path: string;
};

type Props = {
  vaultOpen: boolean;
  activePath: string;
  activeTitle: string;
  refreshKey: number;
  onOpenNote: (path: string) => void;
  onSaveWorkspace: () => Promise<void> | void;
  onLoadWorkspace: (id: string) => Promise<void> | void;
};

export default function BookmarksWorkspacesPanel({
  vaultOpen,
  activePath,
  activeTitle,
  refreshKey,
  onOpenNote,
  onSaveWorkspace,
  onLoadWorkspace,
}: Props) {
  const [bookmarks, setBookmarks] = useState<BookmarkItem[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceListItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!vaultOpen) {
      setBookmarks([]);
      setWorkspaces([]);
      return;
    }
    try {
      const store = await invoke<{ items: BookmarkItem[] }>("list_bookmarks");
      setBookmarks(store.items ?? []);
      const list = await invoke<WorkspaceListItem[]>("list_workspace_layouts");
      setWorkspaces(list ?? []);
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }, [vaultOpen]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const bookmarked = bookmarks.some((b) => b.path === activePath);

  async function toggleCurrent() {
    if (!vaultOpen || !activePath) return;
    setBusy(true);
    try {
      const store = await invoke<{ items: BookmarkItem[] }>("toggle_bookmark", {
        relativePath: activePath,
        title: activeTitle,
      });
      setBookmarks(store.items ?? []);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!vaultOpen) return null;

  return (
    <div className="org-panel" aria-label="Bookmarks and workspaces">
      <h3>Bookmarks</h3>
      <div className="actions compact">
        <button type="button" onClick={() => void toggleCurrent()} disabled={busy || !activePath}>
          {bookmarked ? "Remove bookmark" : "Bookmark note"}
        </button>
      </div>
      <ul className="org-list">
        {bookmarks.length === 0 ? (
          <li className="muted-copy">No bookmarks yet.</li>
        ) : (
          bookmarks.map((b) => (
            <li key={b.path}>
              <button type="button" className="linkish" onClick={() => onOpenNote(b.path)}>
                {b.title || b.path}
              </button>
            </li>
          ))
        )}
      </ul>

      <h3>Workspaces</h3>
      <div className="actions compact">
        <button
          type="button"
          onClick={() => void onSaveWorkspace()}
          disabled={busy}
        >
          Save layout…
        </button>
      </div>
      <ul className="org-list">
        {workspaces.length === 0 ? (
          <li className="muted-copy">No saved layouts.</li>
        ) : (
          workspaces.map((w) => (
            <li key={w.id}>
              <button
                type="button"
                className="linkish"
                onClick={() => void onLoadWorkspace(w.id)}
              >
                {w.title || w.id}
              </button>
            </li>
          ))
        )}
      </ul>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
