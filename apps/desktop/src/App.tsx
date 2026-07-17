import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import MarkdownEditor, { type EditorMode } from "./components/MarkdownEditor";
import FileExplorer from "./components/FileExplorer";
import CommandPalette, { type PaletteCommand } from "./components/CommandPalette";
import LinksPanel from "./components/LinksPanel";
import BasesPanel from "./components/BasesPanel";
import CanvasPanel from "./components/CanvasPanel";
import BookmarksWorkspacesPanel from "./components/BookmarksWorkspacesPanel";
import FootnotesWordCountPanel from "./components/FootnotesWordCountPanel";
import WorkflowSuite from "./components/WorkflowSuite";
import ModelIntelligencePanel from "./components/ModelIntelligencePanel";
import SyncPanel from "./components/SyncPanel";
import { APP_COMMANDS, type CommandId } from "./commands";
import { useHotkeys } from "./hooks/useHotkeys";
import { t } from "./i18n";
import { personaById, PERSONAS, type PersonaId } from "./personas";
import {
  applyThemePrefs,
  loadThemePrefs,
  saveThemePrefs,
  watchSystemReducedMotion,
  type ThemePrefs,
} from "./theme";
import { countWords } from "./markdown/renderMarkdown";
import type { WorkflowIr } from "./types";
import "./App.css";

const DEFAULT_NOTE = "notes/welcome.md";

type Health = { ok: boolean; detail: Record<string, unknown> };

type EditorTab = {
  path: string;
  title: string;
  dirty: boolean;
  pinned?: boolean;
};

type NoteStat = {
  relative_path: string;
  exists: boolean;
  content_hash?: string | null;
};

type PaletteMode = "command" | "switcher" | "search" | null;
type UiMode = "guided" | "studio";
type VaultSurface = "note" | "bases" | "canvas";
/** Primary app focus — progressive disclosure per UX_PRINCIPLES.md */
type FocusView = "workflow" | "notes" | "tools";
type RailSection = "files" | "links" | "org";

function titleFromPath(path: string) {
  const parts = path.replace(/\\/g, "/").split("/");
  const leaf = parts[parts.length - 1] ?? path;
  return leaf.replace(/\.md$/i, "");
}

function defaultWelcome(persona: PersonaId): string {
  const p = personaById(persona);
  return `---
tags: [welcome]
---
# Welcome to BrainFlow

${p.starterNoteBody}

## Ideas

- Study from lecture notes
- Plan a project from a brief
- Summarize a meeting transcript

Try a wikilink once you add another note: [[Daily]]
`;
}

export default function App() {
  const [theme, setTheme] = useState<ThemePrefs>(() => loadThemePrefs());
  const [mode, setMode] = useState<UiMode>("guided");
  const [personaId, setPersonaId] = useState<PersonaId>("student");
  const persona = personaById(personaId);
  const [focusView, setFocusView] = useState<FocusView>("workflow");
  const [railSection, setRailSection] = useState<RailSection>("files");
  const [metaOpen, setMetaOpen] = useState(false);
  const [toolbarMoreOpen, setToolbarMoreOpen] = useState(false);

  const [vaultPath, setVaultPath] = useState("");
  const [onedriveWarning, setOnedriveWarning] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [tabs, setTabs] = useState<EditorTab[]>([]);
  const [activePath, setActivePath] = useState(DEFAULT_NOTE);
  const [splitPath, setSplitPath] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<EditorMode>("source");
  const [vaultSurface, setVaultSurface] = useState<VaultSurface>("note");
  const [jumpHeading, setJumpHeading] = useState<string | null>(null);
  const [jumpBlock, setJumpBlock] = useState<string | null>(null);
  const [dropActive, setDropActive] = useState(false);
  const [bodies, setBodies] = useState<Record<string, string>>({});
  const [savedHashes, setSavedHashes] = useState<Record<string, string>>({});
  const [diskHashes, setDiskHashes] = useState<Record<string, string>>({});
  const [prompt, setPrompt] = useState(persona.defaultGoalPrompt);
  const [health, setHealth] = useState<Health | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowIr | null>(null);
  const [previousWorkflow, setPreviousWorkflow] = useState<WorkflowIr | null>(
    null,
  );
  const [artifactPath, setArtifactPath] = useState("");
  const [runMeta, setRunMeta] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState("Open a vault to begin.");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [explorerKey, setExplorerKey] = useState(0);
  const [linksKey, setLinksKey] = useState(0);
  const [palette, setPalette] = useState<PaletteMode>(null);
  const [notes, setNotes] = useState<{ path: string; name: string }[]>([]);
  const [searchHits, setSearchHits] = useState<
    { path: string; snippet?: string | null }[]
  >([]);
  const [graphPreview, setGraphPreview] = useState("");
  const [externalWarn, setExternalWarn] = useState("");
  const [orgKey, setOrgKey] = useState(0);
  const autosaveTimer = useRef<number | null>(null);
  const vaultOpen = Boolean(vaultPath);

  const noteBody = bodies[activePath] ?? "";
  const activeTab = tabs.find((t) => t.path === activePath);

  useEffect(() => {
    applyThemePrefs(theme);
    saveThemePrefs(theme);
  }, [theme]);

  useEffect(() => {
    return watchSystemReducedMotion(() => applyThemePrefs(loadThemePrefs()));
  }, []);

  useEffect(() => {
    setPrompt(persona.defaultGoalPrompt);
  }, [persona.defaultGoalPrompt]);

  useEffect(() => {
    if (!toolbarMoreOpen) return;
    const onPointer = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest?.(".toolbar-more")) return;
      setToolbarMoreOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setToolbarMoreOpen(false);
    };
    window.addEventListener("mousedown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [toolbarMoreOpen]);

  const llmLabel = useMemo(() => {
    if (!health) return "LLM: unchecked";
    if (!health.ok) return "LLM: unavailable (fail-closed)";
    const model =
      (health.detail.preferred_model as string | undefined) ||
      ((health.detail.models as string[] | undefined)?.[0] ?? "ready");
    return `LLM: ${model}`;
  }, [health]);

  const refreshHealth = useCallback(async () => {
    try {
      const h = await invoke<Health>("llm_health");
      setHealth(h);
      if (!h.ok) {
        setError(
          String(
            (h.detail as { error?: string }).error ??
              "No validated LLM available. AI workflow generation is paused.",
          ),
        );
      } else if (!error.includes("Generation")) {
        setError("");
      }
    } catch (e) {
      setHealth({ ok: false, detail: { error: String(e) } });
      setError(String(e));
    }
  }, [error]);

  const refreshNotes = useCallback(async () => {
    if (!vaultOpen) {
      setNotes([]);
      return;
    }
    try {
      const list = await invoke<{ path: string; name: string }[]>("list_notes");
      setNotes(list);
    } catch {
      setNotes([]);
    }
  }, [vaultOpen]);

  const openNoteInTab = useCallback(
    async (
      path: string,
      content?: string,
      opts?: { heading?: string; block?: string; split?: boolean },
    ) => {
      let body = content;
      if (body === undefined) {
        try {
          body = await invoke<string>("read_note", { relativePath: path });
        } catch {
          body = `# ${titleFromPath(path)}\n\n`;
        }
      }
      setBodies((prev) => ({ ...prev, [path]: body! }));
      setTabs((prev) => {
        if (prev.some((t) => t.path === path)) return prev;
        return [...prev, { path, title: titleFromPath(path), dirty: false }];
      });
      if (opts?.split) {
        setSplitPath(path);
      } else {
        setActivePath(path);
        setVaultSurface("note");
        setFocusView("notes");
      }
      if (opts?.heading || opts?.block) {
        setJumpHeading(opts.heading ?? null);
        setJumpBlock(opts.block ?? null);
        if (editorMode === "source") setEditorMode("live");
      } else {
        setJumpHeading(null);
        setJumpBlock(null);
      }
      try {
        const stat = await invoke<NoteStat>("note_stat", { relativePath: path });
        if (stat.content_hash) {
          setSavedHashes((h) => ({ ...h, [path]: stat.content_hash! }));
          setDiskHashes((h) => ({ ...h, [path]: stat.content_hash! }));
        }
      } catch {
        /* ignore */
      }
      setExternalWarn("");
      setLinksKey((k) => k + 1);
    },
    [editorMode],
  );

  const markDirty = useCallback((path: string, value: string) => {
    setBodies((prev) => ({ ...prev, [path]: value }));
    setTabs((prev) =>
      prev.map((t) => (t.path === path ? { ...t, dirty: true } : t)),
    );
  }, []);

  const saveNote = useCallback(
    async (path?: string) => {
      const target = path ?? activePath;
      if (!vaultPath) {
        setError("Open a vault first.");
        return;
      }
      const content = bodies[target] ?? "";
      setBusy(true);
      setError("");
      try {
        await invoke("save_note", { relativePath: target, content });
        const stat = await invoke<NoteStat>("note_stat", {
          relativePath: target,
        });
        if (stat.content_hash) {
          setSavedHashes((h) => ({ ...h, [target]: stat.content_hash! }));
          setDiskHashes((h) => ({ ...h, [target]: stat.content_hash! }));
        }
        setTabs((prev) =>
          prev.map((t) => (t.path === target ? { ...t, dirty: false } : t)),
        );
        setStatus(`Saved ${target} (atomic write)`);
        setExplorerKey((k) => k + 1);
        setLinksKey((k) => k + 1);
        setExternalWarn("");
        await refreshNotes();
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    },
    [activePath, bodies, refreshNotes, vaultPath],
  );

  useEffect(() => {
    if (!vaultOpen || !activeTab?.dirty) return;
    if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current);
    autosaveTimer.current = window.setTimeout(() => {
      void saveNote(activePath);
    }, 1200);
    return () => {
      if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current);
    };
  }, [noteBody, activeTab?.dirty, activePath, saveNote, vaultOpen]);

  useEffect(() => {
    if (!vaultOpen || !activePath) return;
    const id = window.setInterval(async () => {
      try {
        const stat = await invoke<NoteStat>("note_stat", {
          relativePath: activePath,
        });
        const disk = stat.content_hash ?? "";
        const known = diskHashes[activePath] ?? savedHashes[activePath] ?? "";
        const dirty = tabs.find((t) => t.path === activePath)?.dirty;
        if (disk && known && disk !== known && !dirty) {
          setExternalWarn(
            "Note changed on disk. Reload from disk or keep editing to overwrite on save.",
          );
          setDiskHashes((h) => ({ ...h, [activePath]: disk }));
        } else if (disk) {
          setDiskHashes((h) => ({ ...h, [activePath]: disk }));
        }
      } catch {
        /* ignore */
      }
    }, 4000);
    return () => window.clearInterval(id);
  }, [vaultOpen, activePath, diskHashes, savedHashes, tabs]);

  useEffect(() => {
    (async () => {
      try {
        const session = await invoke<Record<string, unknown>>("load_session");
        if (session.ok && typeof session.last_vault === "string") {
          setVaultPath(session.last_vault);
          setOnedriveWarning(Boolean(session.onedrive_warning));
          const note =
            typeof session.last_note === "string"
              ? session.last_note
              : DEFAULT_NOTE;
          const content =
            typeof session.note_content === "string"
              ? session.note_content
              : defaultWelcome(personaId);
          setBodies({ [note]: content });
          setTabs([{ path: note, title: titleFromPath(note), dirty: false }]);
          setActivePath(note);
          if (session.workflow) setWorkflow(session.workflow as WorkflowIr);
          if (session.run) {
            setRunMeta(session.run as Record<string, unknown>);
            const arts = (session.run as { artifact_paths?: string[] })
              .artifact_paths;
            if (arts?.[0]) setArtifactPath(arts[0]);
          }
          setStatus("Restored previous session.");
          setExplorerKey((k) => k + 1);
        }
      } catch {
        /* first launch */
      }
      await refreshHealth();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void refreshNotes();
  }, [refreshNotes, explorerKey]);

  async function afterVaultOpen(root: string, onedrive: boolean) {
    setVaultPath(root);
    setOnedriveWarning(onedrive);
    try {
      await invoke("ensure_foundations");
    } catch {
      /* stubs best-effort */
    }
    const welcome = defaultWelcome(personaId);
    try {
      const existing = await invoke<string>("read_note", {
        relativePath: DEFAULT_NOTE,
      });
      await openNoteInTab(DEFAULT_NOTE, existing);
    } catch {
      await invoke("save_note", {
        relativePath: DEFAULT_NOTE,
        content: welcome,
      });
      await openNoteInTab(DEFAULT_NOTE, welcome);
    }
    setExplorerKey((k) => k + 1);
    setStatus(`Vault open: ${root}`);
    await refreshNotes();
  }

  const onPickVault = useCallback(async () => {
    setError("");
    try {
      const picked = await invoke<string | null>("pick_vault");
      if (!picked) return;
      const opened = await invoke<{ root: string; onedrive_warning: boolean }>(
        "open_vault",
        { path: picked },
      );
      await afterVaultOpen(opened.root, opened.onedrive_warning);
    } catch (e) {
      setError(String(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personaId, openNoteInTab, refreshNotes]);

  const onCreateVault = useCallback(async () => {
    setError("");
    try {
      const picked = await invoke<string | null>("create_vault_dialog");
      if (!picked) return;
      const opened = await invoke<{ root: string; onedrive_warning: boolean }>(
        "create_vault",
        { path: picked, displayName: "BrainFlow Vault" },
      );
      await afterVaultOpen(opened.root, opened.onedrive_warning);
    } catch (e) {
      setError(String(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personaId, openNoteInTab, refreshNotes]);

  const onGenerate = useCallback(async () => {
    if (!vaultPath) {
      setError("Open a vault first.");
      return;
    }
    setBusy(true);
    setError("");
    setStatus(`Generating schema-valid ${persona.workflowTerm} via LLM…`);
    try {
      await invoke("save_note", {
        relativePath: activePath,
        content: noteBody,
      });
      const result = await invoke<{
        workflow: WorkflowIr;
        run: Record<string, unknown>;
        artifact_path: string;
      }>("generate_workflow_slice", {
        prompt,
        noteRelativePath: activePath,
      });
      setPreviousWorkflow(workflow);
      setWorkflow(result.workflow);
      setRunMeta(result.run);
      setArtifactPath(result.artifact_path);
      setStatus(
        `${persona.workflowTerm} generated, validated, ${persona.artifactTerm} written.`,
      );
      await refreshHealth();
    } catch (e) {
      setError(String(e));
      setStatus(
        "Generation blocked (fail-closed). Vault editing still available.",
      );
    } finally {
      setBusy(false);
    }
  }, [
    vaultPath,
    persona,
    activePath,
    noteBody,
    prompt,
    workflow,
    refreshHealth,
  ]);

  async function reloadFromDisk() {
    try {
      const content = await invoke<string>("read_note", {
        relativePath: activePath,
      });
      setBodies((prev) => ({ ...prev, [activePath]: content }));
      setTabs((prev) =>
        prev.map((t) => (t.path === activePath ? { ...t, dirty: false } : t)),
      );
      const stat = await invoke<NoteStat>("note_stat", {
        relativePath: activePath,
      });
      if (stat.content_hash) {
        setSavedHashes((h) => ({ ...h, [activePath]: stat.content_hash! }));
        setDiskHashes((h) => ({ ...h, [activePath]: stat.content_hash! }));
      }
      setExternalWarn("");
      setStatus(`Reloaded ${activePath} from disk`);
    } catch (e) {
      setError(String(e));
    }
  }

  const onDailyNote = useCallback(async () => {
    try {
      const res = await invoke<{ path: string; content: string }>(
        "open_daily_note",
      );
      await openNoteInTab(res.path, res.content);
      setExplorerKey((k) => k + 1);
      setStatus(`Daily note: ${res.path}`);
    } catch (e) {
      setError(String(e));
    }
  }, [openNoteInTab]);

  const onNewFromTemplate = useCallback(async () => {
    const name = `notes/untitled-${Date.now()}.md`;
    try {
      const body = await invoke<string>("apply_note_template", {
        templateId: "note",
        destRelative: name,
        title: titleFromPath(name),
      });
      await openNoteInTab(name, body);
      setExplorerKey((k) => k + 1);
    } catch (e) {
      setError(String(e));
    }
  }, [openNoteInTab]);

  const onUniqueNote = useCallback(async () => {
    const title = window.prompt("Unique note title (optional):", "") ?? undefined;
    try {
      const res = await invoke<{ path: string; content: string }>(
        "create_unique_note",
        { title: title?.trim() ? title.trim() : null },
      );
      await openNoteInTab(res.path, res.content);
      setExplorerKey((k) => k + 1);
      setStatus(`Unique note: ${res.path}`);
    } catch (e) {
      setError(String(e));
    }
  }, [openNoteInTab]);

  const onRandomNote = useCallback(async () => {
    try {
      const res = await invoke<{ path: string | null }>("random_note");
      if (!res.path) {
        setStatus("No notes in vault for random open.");
        return;
      }
      await openNoteInTab(res.path);
      setStatus(`Random note: ${res.path}`);
    } catch (e) {
      setError(String(e));
    }
  }, [openNoteInTab]);

  const onToggleBookmark = useCallback(async () => {
    if (!vaultOpen || !activePath) return;
    try {
      await invoke("toggle_bookmark", {
        relativePath: activePath,
        title: titleFromPath(activePath),
      });
      setOrgKey((k) => k + 1);
      setStatus(`Bookmarks updated for ${activePath}`);
    } catch (e) {
      setError(String(e));
    }
  }, [vaultOpen, activePath]);

  const onSaveWorkspace = useCallback(async () => {
    if (!vaultOpen) return;
    const title =
      window.prompt("Workspace name:", "Focus")?.trim() || "Focus";
    try {
      const rel = await invoke<string>("save_workspace_layout", {
        layout: {
          schema_version: 1,
          id: title,
          title,
          tabs: tabs.map((t) => ({ path: t.path, pinned: Boolean(t.pinned) })),
          active_path: activePath,
          split_path: splitPath,
          editor_mode: editorMode,
          vault_surface: vaultSurface,
          rail_collapsed: railCollapsed,
        },
      });
      setOrgKey((k) => k + 1);
      setStatus(`Saved workspace layout → ${rel}`);
    } catch (e) {
      setError(String(e));
    }
  }, [
    vaultOpen,
    tabs,
    activePath,
    splitPath,
    editorMode,
    vaultSurface,
    railCollapsed,
  ]);

  const onLoadWorkspace = useCallback(
    async (id?: string) => {
      if (!vaultOpen) return;
      let target = id;
      if (!target) {
        try {
          const list = await invoke<{ id: string; title: string }[]>(
            "list_workspace_layouts",
          );
          if (!list.length) {
            setStatus("No saved workspaces.");
            return;
          }
          const picked =
            window.prompt(
              `Load workspace id (${list.map((w) => w.id).join(", ")}):`,
              list[0].id,
            )?.trim() || "";
          if (!picked) return;
          target = picked;
        } catch (e) {
          setError(String(e));
          return;
        }
      }
      try {
        const layout = await invoke<{
          tabs: { path: string; pinned?: boolean }[];
          active_path: string;
          split_path?: string | null;
          editor_mode?: string;
          vault_surface?: string;
          rail_collapsed?: boolean;
        }>("load_workspace_layout", { id: target });
        const nextTabs: EditorTab[] = [];
        const nextBodies: Record<string, string> = { ...bodies };
        for (const tab of layout.tabs ?? []) {
          if (!tab.path) continue;
          try {
            const content = await invoke<string>("read_note", {
              relativePath: tab.path,
            });
            nextBodies[tab.path] = content;
          } catch {
            nextBodies[tab.path] =
              nextBodies[tab.path] ?? `# ${titleFromPath(tab.path)}\n\n`;
          }
          nextTabs.push({
            path: tab.path,
            title: titleFromPath(tab.path),
            dirty: false,
            pinned: Boolean(tab.pinned),
          });
        }
        if (!nextTabs.length && layout.active_path) {
          nextTabs.push({
            path: layout.active_path,
            title: titleFromPath(layout.active_path),
            dirty: false,
          });
        }
        setBodies(nextBodies);
        setTabs(nextTabs);
        setActivePath(layout.active_path || nextTabs[0]?.path || DEFAULT_NOTE);
        setSplitPath(layout.split_path ?? null);
        if (
          layout.editor_mode === "source" ||
          layout.editor_mode === "live" ||
          layout.editor_mode === "reading"
        ) {
          setEditorMode(layout.editor_mode);
        }
        if (
          layout.vault_surface === "note" ||
          layout.vault_surface === "bases" ||
          layout.vault_surface === "canvas"
        ) {
          setVaultSurface(layout.vault_surface);
        }
        setRailCollapsed(Boolean(layout.rail_collapsed));
        setOrgKey((k) => k + 1);
        setStatus(`Restored workspace “${target}”`);
      } catch (e) {
        setError(String(e));
      }
    },
    [vaultOpen, bodies],
  );

  const onApplyProperty = useCallback(
    async (key: string, value: string) => {
      if (!vaultOpen || !activePath) return;
      const nextVal =
        window.prompt(`Set property “${key}” on ${activePath}:`, value) ?? null;
      if (nextVal === null) return;
      try {
        const content = await invoke<string>("set_note_property", {
          relativePath: activePath,
          key,
          value: nextVal,
        });
        setBodies((prev) => ({ ...prev, [activePath]: content }));
        setTabs((prev) =>
          prev.map((t) =>
            t.path === activePath ? { ...t, dirty: false } : t,
          ),
        );
        setLinksKey((k) => k + 1);
        setExplorerKey((k) => k + 1);
        setStatus(`Set ${key} on ${activePath}`);
      } catch (e) {
        setError(String(e));
      }
    },
    [vaultOpen, activePath],
  );

  const showGraph = useCallback(
    async (local: boolean) => {
      try {
        const g = await invoke<{
          nodes: unknown[];
          edges: unknown[];
        }>("knowledge_graph", {
          focusPath: local ? activePath : null,
          localOnly: local,
        });
        setGraphPreview(
          `${local ? "Local" : "Global"} knowledge · ${g.nodes?.length ?? 0} nodes · ${g.edges?.length ?? 0} edges`,
        );
        setLinksKey((k) => k + 1);
      } catch (e) {
        setError(String(e));
      }
    },
    [activePath],
  );

  const restoreLatestSnapshot = useCallback(async () => {
    try {
      const snaps = await invoke<{ id: string }[]>("list_note_snapshots", {
        relativePath: activePath,
      });
      if (!snaps.length) {
        setStatus("No recovery snapshots for this note.");
        return;
      }
      const content = await invoke<string>("restore_note_snapshot", {
        relativePath: activePath,
        snapshotId: snaps[0].id,
      });
      await openNoteInTab(activePath, content);
      setStatus(`Restored snapshot ${snaps[0].id}`);
    } catch (e) {
      setError(String(e));
    }
  }, [activePath, openNoteInTab]);

  const onRenameNote = useCallback(async () => {
    if (!vaultOpen || !activePath) return;
    const next = window.prompt(
      "Rename note to (vault-relative .md path):",
      activePath,
    );
    if (!next || next === activePath) return;
    try {
      const res = await invoke<{
        to_path: string;
        notes_updated: number;
        links_rewritten: number;
      }>("rename_note", { fromPath: activePath, toPath: next });
      setBodies((prev) => {
        const copy = { ...prev };
        const body = copy[activePath];
        delete copy[activePath];
        if (body !== undefined) copy[res.to_path] = body;
        return copy;
      });
      setTabs((prev) =>
        prev.map((t) =>
          t.path === activePath
            ? { ...t, path: res.to_path, title: titleFromPath(res.to_path) }
            : t,
        ),
      );
      if (splitPath === activePath) setSplitPath(res.to_path);
      setActivePath(res.to_path);
      setExplorerKey((k) => k + 1);
      setLinksKey((k) => k + 1);
      await refreshNotes();
      setStatus(
        `Renamed → ${res.to_path} (${res.links_rewritten} links in ${res.notes_updated} notes)`,
      );
    } catch (e) {
      setError(String(e));
    }
  }, [vaultOpen, activePath, splitPath, refreshNotes]);

  const getNoteBody = useCallback(
    (path: string) => {
      if (bodies[path] !== undefined) return bodies[path];
      return null;
    },
    [bodies],
  );

  const ensureEmbedBody = useCallback(
    async (path: string) => {
      if (bodies[path] !== undefined) return bodies[path];
      try {
        const content = await invoke<string>("read_note", {
          relativePath: path,
        });
        setBodies((prev) => ({ ...prev, [path]: content }));
        return content;
      } catch {
        return null;
      }
    },
    [bodies],
  );

  // Prefetch note bodies for embeds when notes list changes
  useEffect(() => {
    if (!vaultOpen) return;
    for (const n of notes.slice(0, 40)) {
      if (bodies[n.path] === undefined) {
        void ensureEmbedBody(n.path);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notes, vaultOpen]);

  const onDropFiles = useCallback(
    async (files: FileList | null) => {
      if (!vaultOpen || !files?.length) return;
      setDropActive(false);
      for (const file of Array.from(files)) {
        try {
          const text = await file.text();
          const safe = file.name.replace(/[^\w.\- ()[\]]+/g, "_");
          const dest = safe.toLowerCase().endsWith(".md")
            ? `notes/${safe}`
            : `attachments/${safe}`;
          const rel = await invoke<string>("import_dropped_text", {
            destRelative: dest,
            content: text,
          });
          setExplorerKey((k) => k + 1);
          if (rel.toLowerCase().endsWith(".md")) {
            await openNoteInTab(rel, text);
          }
          setStatus(`Imported ${rel}`);
          await refreshNotes();
        } catch (e) {
          setError(String(e));
        }
      }
    },
    [vaultOpen, openNoteInTab, refreshNotes],
  );

  const onSearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchHits([]);
      return;
    }
    try {
      const hits = await invoke<{ path: string; snippet?: string | null }[]>(
        "search_vault",
        { query },
      );
      setSearchHits(hits);
    } catch {
      setSearchHits([]);
    }
  }, []);

  const runCommand = useCallback(
    async (id: CommandId) => {
      switch (id) {
        case "vault.open":
          await onPickVault();
          break;
        case "vault.create":
          await onCreateVault();
          break;
        case "note.save":
          await saveNote();
          break;
        case "note.daily":
          await onDailyNote();
          break;
        case "note.template":
          await onNewFromTemplate();
          break;
        case "note.unique":
          await onUniqueNote();
          break;
        case "note.random":
          await onRandomNote();
          break;
        case "note.bookmark":
          await onToggleBookmark();
          break;
        case "workspace.save":
          await onSaveWorkspace();
          break;
        case "workspace.load":
          await onLoadWorkspace();
          break;
        case "view.wordCount": {
          const c = countWords(noteBody);
          setStatus(
            `Word count · ${c.words} words · ${c.characters} characters (${c.charactersNoSpaces} non-space)`,
          );
          break;
        }
        case "note.switcher":
          setPalette("switcher");
          break;
        case "note.search":
          setPalette("search");
          break;
        case "graph.local":
          await showGraph(true);
          break;
        case "graph.global":
          await showGraph(false);
          break;
        case "vault.reindex": {
          const n = await invoke<number>("reindex_notes");
          setStatus(`Reindexed ${n} notes`);
          break;
        }
        case "note.restore":
          await restoreLatestSnapshot();
          break;
        case "note.rename":
          await onRenameNote();
          break;
        case "editor.source":
          setEditorMode("source");
          setVaultSurface("note");
          setFocusView("notes");
          break;
        case "editor.live":
          setEditorMode("live");
          setVaultSurface("note");
          setFocusView("notes");
          break;
        case "editor.reading":
          setEditorMode("reading");
          setVaultSurface("note");
          setFocusView("notes");
          break;
        case "view.bases":
          setFocusView("notes");
          setVaultSurface("bases");
          break;
        case "view.canvas":
          setFocusView("notes");
          setVaultSurface("canvas");
          break;
        case "view.workflow":
          setFocusView("workflow");
          break;
        case "view.notes":
          setFocusView("notes");
          break;
        case "view.tools":
          setFocusView("tools");
          setMode("studio");
          break;
        case "pane.split":
          if (activePath) setSplitPath(activePath);
          break;
        case "pane.closeSplit":
          setSplitPath(null);
          break;
        case "tab.pin":
          setTabs((prev) =>
            prev.map((t) =>
              t.path === activePath ? { ...t, pinned: !t.pinned } : t,
            ),
          );
          break;
        case "workflow.generate":
          await onGenerate();
          break;
        case "mode.toggle":
          setMode((m) => (m === "guided" ? "studio" : "guided"));
          break;
        case "llm.refresh":
          await refreshHealth();
          break;
        case "palette.open":
          setPalette("command");
          break;
        case "export.publishStub":
          setStatus(
            "Publish pipeline stub — remote publish requires explicit approval (not wired).",
          );
          break;
      }
    },
    [
      onPickVault,
      onCreateVault,
      saveNote,
      onDailyNote,
      onNewFromTemplate,
      onUniqueNote,
      onRandomNote,
      onToggleBookmark,
      onSaveWorkspace,
      onLoadWorkspace,
      showGraph,
      restoreLatestSnapshot,
      onRenameNote,
      onGenerate,
      refreshHealth,
      activePath,
      noteBody,
    ],
  );

  useHotkeys(
    useMemo(() => {
      const handlers: Partial<Record<CommandId, () => void>> = {};
      for (const c of APP_COMMANDS) {
        handlers[c.id] = () => {
          void runCommand(c.id);
        };
      }
      return handlers;
    }, [runCommand]),
  );

  const paletteCommands: PaletteCommand[] = useMemo(
    () =>
      APP_COMMANDS.map((c) => ({
        id: c.id,
        label: c.title,
        hint: c.shortcut,
        run: () => runCommand(c.id),
      })),
    [runCommand],
  );

  function closeTab(path: string) {
    const tab = tabs.find((t) => t.path === path);
    if (tab?.pinned) {
      setStatus(`Unpin “${tab.title}” before closing.`);
      return;
    }
    setTabs((prev) => {
      const next = prev.filter((t) => t.path !== path);
      if (path === activePath) {
        const fallback = next[next.length - 1]?.path ?? DEFAULT_NOTE;
        setActivePath(fallback);
      }
      return next;
    });
    if (splitPath === path) setSplitPath(null);
  }

  function togglePin(path: string) {
    setTabs((prev) =>
      prev.map((t) => (t.path === path ? { ...t, pinned: !t.pinned } : t)),
    );
  }

  const editorNode = (
    path: string,
    opts?: { isSplit?: boolean },
  ) => (
    <MarkdownEditor
      value={bodies[path] ?? ""}
      onChange={(v) => markDirty(path, v)}
      mode={editorMode}
      readOnly={!vaultOpen}
      notePaths={notes}
      getNoteBody={getNoteBody}
      onOpenNote={(p, heading, block) =>
        void openNoteInTab(p, undefined, {
          heading,
          block,
          split: opts?.isSplit ? false : undefined,
        })
      }
      jumpHeading={path === activePath ? jumpHeading : null}
      jumpBlock={path === activePath ? jumpBlock : null}
      slashExtra={[
        {
          id: "unique",
          label: "Create unique note",
          run: () => void onUniqueNote(),
        },
        {
          id: "daily",
          label: "Open daily note",
          run: () => void onDailyNote(),
        },
        {
          id: "random",
          label: "Open random note",
          run: () => void onRandomNote(),
        },
      ]}
    />
  );

  const effectiveFocus: FocusView =
    mode === "guided" && focusView === "tools" ? "workflow" : focusView;

  const vaultSidebar = (
    <aside
      className={`panel vault-rail${railCollapsed ? " is-collapsed" : ""}`}
      aria-label="Vault"
    >
      <div className="rail-head">
        <h2>Vault</h2>
        <button
          type="button"
          className="ghost icon-btn"
          onClick={() => setRailCollapsed((v) => !v)}
          aria-expanded={!railCollapsed}
          aria-label={railCollapsed ? "Expand vault rail" : "Collapse vault rail"}
        >
          {railCollapsed ? "▸" : "◂"}
        </button>
      </div>
      {!railCollapsed ? (
        <>
          <div className="actions vault-actions">
            <button type="button" onClick={() => void onPickVault()} disabled={busy}>
              Open
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => void onCreateVault()}
              disabled={busy}
            >
              Create
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => void onDailyNote()}
              disabled={busy || !vaultOpen}
            >
              Daily
            </button>
          </div>
          <p className="path vault-path" title={vaultPath || undefined}>
            {vaultPath || "No vault selected"}
          </p>
          {onedriveWarning ? (
            <p className="warn" role="status">
              Cloud sync folder detected. Prefer a local disk vault; indexes stay
              under %LOCALAPPDATA%\BrainFlow.
            </p>
          ) : null}
          {!vaultOpen ? (
            <div className="empty-card" role="status">
              <p className="empty-title">Open a vault to begin</p>
              <p className="muted-copy">
                Pick a local folder. Notes stay on disk; workflows write derived
                artifacts under .brainflow/.
              </p>
              <div className="actions">
                <button type="button" className="primary" onClick={() => void onPickVault()}>
                  Open vault
                </button>
                <button type="button" className="ghost" onClick={() => void onCreateVault()}>
                  Create vault
                </button>
              </div>
            </div>
          ) : (
            <>
              <div
                className="rail-tabs"
                role="tablist"
                aria-label="Vault sections"
              >
                {(
                  [
                    ["files", "Files"],
                    ["links", "Links"],
                    ["org", "Organize"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={railSection === id}
                    className={`rail-tab${railSection === id ? " active" : ""}`}
                    onClick={() => setRailSection(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {railSection === "files" ? (
                <FileExplorer
                  vaultOpen={vaultOpen}
                  activePath={activePath}
                  onOpenNote={(p) => void openNoteInTab(p)}
                  refreshKey={explorerKey}
                />
              ) : null}
              {railSection === "links" ? (
                <LinksPanel
                  vaultOpen={vaultOpen}
                  notePath={activePath}
                  onOpenNote={(p) => void openNoteInTab(p)}
                  onApplyProperty={(k, v) => void onApplyProperty(k, v)}
                  refreshKey={linksKey}
                />
              ) : null}
              {railSection === "org" ? (
                <>
                  <BookmarksWorkspacesPanel
                    vaultOpen={vaultOpen}
                    activePath={activePath}
                    activeTitle={titleFromPath(activePath)}
                    refreshKey={orgKey}
                    onOpenNote={(p) => void openNoteInTab(p)}
                    onSaveWorkspace={() => void onSaveWorkspace()}
                    onLoadWorkspace={(id) => void onLoadWorkspace(id)}
                  />
                  <FootnotesWordCountPanel
                    vaultOpen={vaultOpen}
                    notePath={activePath}
                    body={noteBody}
                  />
                </>
              ) : null}
            </>
          )}
        </>
      ) : null}
    </aside>
  );

  const notesStage = (
    <section
      className={`panel editor-panel${dropActive ? " drop-active" : ""}`}
      onDragOver={(e) => {
        if (!vaultOpen) return;
        e.preventDefault();
        setDropActive(true);
      }}
      onDragLeave={() => setDropActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        void onDropFiles(e.dataTransfer.files);
      }}
    >
      <div className="surface-tabs" role="tablist" aria-label="Vault surface">
        <button
          type="button"
          className={`segment${vaultSurface === "note" ? " active" : ""}`}
          onClick={() => setVaultSurface("note")}
        >
          Note
        </button>
        <button
          type="button"
          className={`segment${vaultSurface === "bases" ? " active" : ""}`}
          onClick={() => setVaultSurface("bases")}
        >
          Bases
        </button>
        <button
          type="button"
          className={`segment${vaultSurface === "canvas" ? " active" : ""}`}
          onClick={() => setVaultSurface("canvas")}
        >
          Canvas
        </button>
      </div>

      {vaultSurface === "bases" ? (
        <BasesPanel
          vaultOpen={vaultOpen}
          onOpenNote={(p) => void openNoteInTab(p)}
          onNoteMutated={(path, content) => {
            setBodies((prev) => ({ ...prev, [path]: content }));
            setLinksKey((k) => k + 1);
          }}
          refreshKey={explorerKey}
        />
      ) : null}

      {vaultSurface === "canvas" ? (
        <CanvasPanel
          vaultOpen={vaultOpen}
          onOpenNote={(p) => void openNoteInTab(p)}
          refreshKey={explorerKey}
        />
      ) : null}

      {vaultSurface === "note" ? (
        <>
          <div className="tab-bar" role="tablist" aria-label="Open notes">
            {tabs.map((tab) => (
              <div
                key={tab.path}
                className={`tab${tab.path === activePath ? " active" : ""}${tab.pinned ? " pinned" : ""}`}
                role="tab"
                aria-selected={tab.path === activePath}
              >
                <button
                  type="button"
                  className="tab-pin"
                  aria-label={tab.pinned ? `Unpin ${tab.title}` : `Pin ${tab.title}`}
                  onClick={() => togglePin(tab.path)}
                >
                  {tab.pinned ? "◆" : "◇"}
                </button>
                <button
                  type="button"
                  className="tab-main"
                  onClick={() => setActivePath(tab.path)}
                  onDoubleClick={() => setSplitPath(tab.path)}
                  title="Double-click to open in split pane"
                >
                  {tab.title}
                  {tab.dirty ? " •" : ""}
                </button>
                <button
                  type="button"
                  className="tab-close"
                  aria-label={`Close ${tab.title}`}
                  onClick={() => closeTab(tab.path)}
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              className="ghost tab-new"
              disabled={!vaultOpen || busy}
              onClick={() => void onNewFromTemplate()}
              title="New from template"
            >
              +
            </button>
          </div>

          {externalWarn ? (
            <div className="external-warn" role="status">
              <span>{externalWarn}</span>
              <button type="button" onClick={() => void reloadFromDisk()}>
                Reload
              </button>
            </div>
          ) : null}

          <div className="editor-toolbar">
            <code className="path">{activePath}</code>
            <div className="mode-toggle" role="group" aria-label="Editor mode">
              {(
                [
                  ["source", "Source"],
                  ["live", "Live"],
                  ["reading", "Reading"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`segment${editorMode === id ? " active" : ""}`}
                  onClick={() => setEditorMode(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="primary"
              onClick={() => void saveNote()}
              disabled={busy || !vaultOpen || !activeTab?.dirty}
            >
              Save
            </button>
            <div className="toolbar-more">
              <button
                type="button"
                className="ghost"
                aria-expanded={toolbarMoreOpen}
                aria-haspopup="menu"
                disabled={!vaultOpen}
                onClick={() => setToolbarMoreOpen((v) => !v)}
              >
                More
              </button>
              {toolbarMoreOpen ? (
                <div className="toolbar-menu" role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setToolbarMoreOpen(false);
                      void onRenameNote();
                    }}
                  >
                    Rename…
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setToolbarMoreOpen(false);
                      setSplitPath((p) => (p ? null : activePath));
                    }}
                  >
                    {splitPath ? "Close split" : "Split pane"}
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setToolbarMoreOpen(false);
                      void showGraph(true);
                    }}
                  >
                    Local graph
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setToolbarMoreOpen(false);
                      void showGraph(false);
                    }}
                  >
                    Global graph
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setToolbarMoreOpen(false);
                      void onToggleBookmark();
                    }}
                  >
                    Bookmark
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setToolbarMoreOpen(false);
                      void onSaveWorkspace();
                    }}
                  >
                    Save workspace
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    disabled={busy || !vaultOpen}
                    onClick={() => {
                      setToolbarMoreOpen(false);
                      void onUniqueNote();
                    }}
                  >
                    Unique note
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    disabled={busy || !vaultOpen}
                    onClick={() => {
                      setToolbarMoreOpen(false);
                      void onRandomNote();
                    }}
                  >
                    Random note
                  </button>
                </div>
              ) : null}
            </div>
          </div>
          {graphPreview ? <p className="muted-copy">{graphPreview}</p> : null}
          {dropActive ? (
            <p className="drop-hint" role="status">
              Drop files to import into the vault
            </p>
          ) : null}

          <div className={`editor-shell${splitPath ? " has-split" : ""}`}>
            <div className="editor-pane">{editorNode(activePath)}</div>
            {splitPath ? (
              <div className="editor-pane split-pane">
                <div className="split-head">
                  <code>{splitPath}</code>
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => setSplitPath(null)}
                  >
                    Close
                  </button>
                </div>
                {editorNode(splitPath, { isSplit: true })}
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );

  const workflowStage = (
    <section className="panel workflow-panel stage-panel">
      <header className="stage-head">
        <div>
          <h2>Workflow Suite</h2>
          <p className="stage-sub">
            {mode === "guided"
              ? `${persona.workflowTerm} · ${persona.explanationDepth} explanations`
              : "Graph edit, budgets, models, and sync"}
          </p>
        </div>
        {!vaultOpen ? (
          <button type="button" className="ghost" onClick={() => void onPickVault()}>
            Open vault first
          </button>
        ) : null}
      </header>

      {!vaultOpen ? (
        <div className="empty-card hero-empty" role="status">
          <p className="empty-title">Start with a vault, then a goal</p>
          <p className="muted-copy">
            Open or create a local vault, confirm the LLM is ready, then generate
            a {persona.workflowTerm}.
          </p>
          <div className="actions">
            <button type="button" className="primary" onClick={() => void onPickVault()}>
              Open vault
            </button>
            <button type="button" onClick={() => void onCreateVault()}>
              Create vault
            </button>
          </div>
        </div>
      ) : null}

      {vaultOpen && health?.ok === false ? (
        <div className="setup-card" role="alert">
          <p className="empty-title">LLM unavailable — AI workflows paused</p>
          <p className="muted-copy">
            {error ||
              "Start Ollama (or your configured provider), pull a model, then recheck."}
          </p>
          <button
            type="button"
            className="primary"
            onClick={() => void refreshHealth()}
            disabled={busy}
          >
            Recheck LLM
          </button>
        </div>
      ) : null}

      <label className="field">
        <span>Goal</span>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={mode === "guided" ? 4 : 3}
          placeholder={`Describe the ${persona.workflowTerm} you want…`}
          disabled={!vaultOpen}
        />
      </label>
      <div className="actions workflow-cta">
        <button
          type="button"
          className="primary"
          onClick={() => void onGenerate()}
          disabled={busy || !vaultPath || health?.ok === false}
        >
          Generate {persona.workflowTerm}
        </button>
        <span className="kbd-hint">
          <kbd>Ctrl</kbd>+<kbd>Enter</kbd>
        </span>
      </div>
      <p className="status" role="status">
        {status}
      </p>
      {error && health?.ok !== false ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      <WorkflowSuite
        workflow={workflow}
        previousWorkflow={previousWorkflow}
        liveMessage={status}
      />

      <details
        className="meta-details"
        open={metaOpen}
        onToggle={(e) => setMetaOpen((e.target as HTMLDetailsElement).open)}
      >
        <summary>
          {persona.artifactTerm} & run metadata
        </summary>
        <div className="meta-grid">
          <div>
            <h3>{persona.artifactTerm}</h3>
            <code>{artifactPath || "—"}</code>
          </div>
          <div>
            <h3>Run metadata</h3>
            <pre>{runMeta ? JSON.stringify(runMeta, null, 2) : "—"}</pre>
          </div>
        </div>
      </details>
    </section>
  );

  const toolsStage = (
    <section className="panel tools-panel stage-panel">
      <header className="stage-head">
        <div>
          <h2>Studio tools</h2>
          <p className="stage-sub">Models, sync, and display preferences</p>
        </div>
      </header>
      <ModelIntelligencePanel compact />
      <SyncPanel vaultOpen={vaultOpen} />
      <fieldset className="prefs-fieldset">
        <legend>Display</legend>
        <label className="check">
          <input
            type="checkbox"
            checked={theme.contrast === "high"}
            onChange={(e) =>
              setTheme((t0) => ({
                ...t0,
                contrast: e.target.checked ? "high" : "default",
              }))
            }
          />
          High contrast
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={theme.density === "compact"}
            onChange={(e) =>
              setTheme((t0) => ({
                ...t0,
                density: e.target.checked ? "compact" : "comfortable",
              }))
            }
          />
          Compact density
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={theme.reduceMotion}
            onChange={(e) =>
              setTheme((t0) => ({
                ...t0,
                reduceMotion: e.target.checked,
              }))
            }
          />
          Reduce motion
        </label>
      </fieldset>
    </section>
  );

  return (
    <div className="app" data-mode={mode} data-focus={effectiveFocus}>
      <a className="skip-link" href="#main-stage">
        Skip to main content
      </a>
      <header className="top">
        <div className="brand">
          <span className="mark" aria-hidden />
          <div>
            <h1>BrainFlow</h1>
            <p className="tagline">Local-first workflow suite</p>
          </div>
        </div>
        <div className="chrome-controls">
          <button
            type="button"
            className="search-affordance"
            onClick={() => setPalette("command")}
            title="Command palette (Ctrl+K)"
          >
            <span>Search or run a command…</span>
            <kbd>Ctrl K</kbd>
          </button>
          <div className="mode-toggle" role="group" aria-label="Experience mode">
            <button
              type="button"
              className={`segment${mode === "guided" ? " active" : ""}`}
              onClick={() => {
                setMode("guided");
                if (focusView === "tools") setFocusView("workflow");
              }}
            >
              {t("mode.guided", "Guided")}
            </button>
            <button
              type="button"
              className={`segment${mode === "studio" ? " active" : ""}`}
              onClick={() => setMode("studio")}
            >
              {t("mode.studio", "Studio")}
            </button>
          </div>
          <label className="persona-select">
            <span className="sr-only">Persona</span>
            <select
              value={personaId}
              onChange={(e) => setPersonaId(e.target.value as PersonaId)}
              title="Persona vocabulary"
            >
              {PERSONAS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <div className="health" data-ok={health?.ok ?? false} title={llmLabel}>
            <span className="health-dot" aria-hidden />
            <span className="health-label">{llmLabel}</span>
            <button
              type="button"
              className="ghost"
              onClick={() => void refreshHealth()}
              disabled={busy}
            >
              Recheck
            </button>
          </div>
        </div>
      </header>

      <div className="shell">
        <nav className="activity-rail" aria-label="Primary navigation">
          <button
            type="button"
            className={`activity-btn${effectiveFocus === "workflow" ? " active" : ""}`}
            aria-current={effectiveFocus === "workflow" ? "page" : undefined}
            onClick={() => setFocusView("workflow")}
            title="Workflow Suite (Ctrl+1)"
          >
            <span className="activity-icon" aria-hidden>
              ◇
            </span>
            <span className="activity-label">Workflow</span>
          </button>
          <button
            type="button"
            className={`activity-btn${effectiveFocus === "notes" ? " active" : ""}`}
            aria-current={effectiveFocus === "notes" ? "page" : undefined}
            onClick={() => setFocusView("notes")}
            title="Notes & vault (Ctrl+2)"
          >
            <span className="activity-icon" aria-hidden>
              ≡
            </span>
            <span className="activity-label">Notes</span>
          </button>
          {mode === "studio" ? (
            <button
              type="button"
              className={`activity-btn${effectiveFocus === "tools" ? " active" : ""}`}
              aria-current={effectiveFocus === "tools" ? "page" : undefined}
              onClick={() => setFocusView("tools")}
              title="Studio tools (Ctrl+3)"
            >
              <span className="activity-icon" aria-hidden>
                ✶
              </span>
              <span className="activity-label">Tools</span>
            </button>
          ) : null}
        </nav>

        <main
          id="main-stage"
          className={`layout layout-focus layout-${effectiveFocus}${
            effectiveFocus === "notes" && railCollapsed ? " rail-collapsed" : ""
          }`}
        >
          {effectiveFocus === "workflow" ? workflowStage : null}
          {effectiveFocus === "notes" ? (
            <>
              {vaultSidebar}
              {notesStage}
            </>
          ) : null}
          {effectiveFocus === "tools" ? toolsStage : null}
        </main>
      </div>

      <CommandPalette
        open={palette !== null}
        mode={palette === null ? "command" : palette}
        commands={paletteCommands}
        notes={notes}
        searchHits={searchHits}
        onClose={() => setPalette(null)}
        onOpenNote={(p) => void openNoteInTab(p)}
        onSearch={onSearch}
      />
    </div>
  );
}
