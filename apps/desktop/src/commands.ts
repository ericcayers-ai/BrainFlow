export type CommandId =
  | "vault.open"
  | "vault.create"
  | "note.save"
  | "note.daily"
  | "note.template"
  | "note.unique"
  | "note.random"
  | "note.switcher"
  | "note.search"
  | "note.rename"
  | "note.restore"
  | "note.bookmark"
  | "workspace.save"
  | "workspace.load"
  | "graph.local"
  | "graph.global"
  | "workflow.generate"
  | "mode.toggle"
  | "llm.refresh"
  | "palette.open"
  | "export.publishStub"
  | "vault.reindex"
  | "editor.source"
  | "editor.live"
  | "editor.reading"
  | "view.bases"
  | "view.canvas"
  | "pane.split"
  | "pane.closeSplit"
  | "tab.pin"
  | "view.wordCount";

export interface AppCommand {
  id: CommandId;
  title: string;
  /** Display chord; actual binding handled in useHotkeys */
  shortcut?: string;
  keywords?: string[];
}

export const APP_COMMANDS: AppCommand[] = [
  {
    id: "vault.open",
    title: "Open vault",
    shortcut: "Ctrl+O",
    keywords: ["folder", "workspace"],
  },
  {
    id: "vault.create",
    title: "Create vault",
    keywords: ["new", "folder"],
  },
  {
    id: "note.save",
    title: "Save note",
    shortcut: "Ctrl+S",
    keywords: ["write", "persist"],
  },
  {
    id: "note.daily",
    title: "Open daily note",
    keywords: ["today", "journal"],
  },
  {
    id: "note.template",
    title: "New note from template",
    keywords: ["create", "stub"],
  },
  {
    id: "note.unique",
    title: "Create unique note",
    keywords: ["zettel", "timestamp", "id"],
  },
  {
    id: "note.random",
    title: "Open random note",
    keywords: ["surprise", "shuffle"],
  },
  {
    id: "note.bookmark",
    title: "Toggle bookmark for current note",
    keywords: ["favorite", "star"],
  },
  {
    id: "workspace.save",
    title: "Save workspace layout",
    keywords: ["tabs", "layout", "session"],
  },
  {
    id: "workspace.load",
    title: "Load workspace layout",
    keywords: ["tabs", "restore"],
  },
  {
    id: "note.switcher",
    title: "Quick switcher",
    shortcut: "Ctrl+P",
    keywords: ["jump", "fuzzy", "files"],
  },
  {
    id: "note.search",
    title: "Search vault",
    shortcut: "Ctrl+Shift+F",
    keywords: ["fts", "find", "tag"],
  },
  {
    id: "graph.local",
    title: "Local knowledge graph",
    keywords: ["backlinks", "neighborhood"],
  },
  {
    id: "graph.global",
    title: "Global knowledge graph",
    keywords: ["vault", "links"],
  },
  {
    id: "vault.reindex",
    title: "Reindex vault (FTS)",
    keywords: ["sqlite", "search"],
  },
  {
    id: "note.restore",
    title: "Restore latest recovery snapshot",
    keywords: ["snapshot", "undo", "crash"],
  },
  {
    id: "note.rename",
    title: "Rename note (update wikilinks)",
    keywords: ["move", "refactor", "links"],
  },
  {
    id: "editor.source",
    title: "Editor: source mode",
    keywords: ["markdown", "cm"],
  },
  {
    id: "editor.live",
    title: "Editor: live preview",
    keywords: ["preview", "gfm"],
  },
  {
    id: "editor.reading",
    title: "Editor: reading mode",
    keywords: ["preview", "readonly"],
  },
  {
    id: "view.bases",
    title: "Open Bases table",
    keywords: ["properties", "filter", "sort", "formula"],
  },
  {
    id: "view.canvas",
    title: "Open Canvas board",
    keywords: ["spatial", "json canvas"],
  },
  {
    id: "view.wordCount",
    title: "Show word count",
    keywords: ["stats", "characters"],
  },
  {
    id: "pane.split",
    title: "Split pane with current note",
    keywords: ["side", "dual"],
  },
  {
    id: "pane.closeSplit",
    title: "Close split pane",
    keywords: ["unsplit"],
  },
  {
    id: "tab.pin",
    title: "Pin / unpin current tab",
    keywords: ["sticky"],
  },
  {
    id: "workflow.generate",
    title: "Generate workflow",
    shortcut: "Ctrl+Enter",
    keywords: ["llm", "ai", "plan"],
  },
  {
    id: "mode.toggle",
    title: "Toggle Guided / Studio",
    shortcut: "Ctrl+Shift+M",
    keywords: ["guided", "studio", "experience"],
  },
  {
    id: "llm.refresh",
    title: "Recheck LLM health",
    shortcut: "Ctrl+Shift+L",
    keywords: ["ollama", "provider"],
  },
  {
    id: "palette.open",
    title: "Open command palette",
    shortcut: "Ctrl+K",
    keywords: ["commands", "search"],
  },
  {
    id: "export.publishStub",
    title: "Export / publish static site (stub)",
    shortcut: "Ctrl+Shift+E",
    keywords: ["publish", "html", "static"],
  },
];

export function filterCommands(query: string): AppCommand[] {
  const q = query.trim().toLowerCase();
  if (!q) return APP_COMMANDS;
  return APP_COMMANDS.filter((c) => {
    const hay = [c.title, c.id, ...(c.keywords ?? [])].join(" ").toLowerCase();
    return hay.includes(q);
  });
}
