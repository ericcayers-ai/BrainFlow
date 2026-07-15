import { useEffect, useMemo, useRef, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { markdown } from "@codemirror/lang-markdown";
import { EditorView } from "@codemirror/view";
import {
  countWords,
  renderMarkdown,
  scrollPreviewToTarget,
} from "../markdown/renderMarkdown";
import SlashMenu, { type SlashCommand } from "./SlashMenu";
import "katex/dist/katex.min.css";

export type EditorMode = "source" | "live" | "reading";

type Props = {
  value: string;
  onChange: (value: string) => void;
  mode: EditorMode;
  readOnly?: boolean;
  notePaths?: { path: string; name: string }[];
  getNoteBody?: (path: string) => string | null;
  onOpenNote?: (path: string, heading?: string, block?: string) => void;
  jumpHeading?: string | null;
  jumpBlock?: string | null;
  slashExtra?: SlashCommand[];
};

const theme = EditorView.theme({
  "&": {
    height: "100%",
    fontSize: "0.92rem",
    backgroundColor: "#0d1612",
  },
  ".cm-scroller": {
    fontFamily: 'var(--font-mono), "IBM Plex Mono", Consolas, monospace',
    lineHeight: "1.5",
  },
  ".cm-content": {
    caretColor: "#3dbf7a",
  },
  "&.cm-focused .cm-cursor": {
    borderLeftColor: "#3dbf7a",
  },
  ".cm-gutters": {
    backgroundColor: "#0a120e",
    color: "#6f8678",
    border: "none",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "#152018",
  },
  ".cm-activeLine": {
    backgroundColor: "#15201855",
  },
});

function resolveTarget(
  target: string,
  notes: { path: string; name: string }[],
): string | null {
  const t = target.replace(/\\/g, "/").toLowerCase();
  const withMd = t.endsWith(".md") ? t : `${t}.md`;
  for (const n of notes) {
    const p = n.path.replace(/\\/g, "/").toLowerCase();
    const stem = (n.name || p).replace(/\.md$/i, "").toLowerCase();
    if (
      p === t ||
      p === withMd ||
      stem === t.replace(/\.md$/, "") ||
      p.endsWith(`/${withMd}`)
    ) {
      return n.path;
    }
  }
  return null;
}

function stripBodyPreview(raw: string, max = 280): string {
  let src = raw.replace(/^\uFEFF/, "");
  if (src.startsWith("---")) {
    const end = src.indexOf("\n---", 3);
    if (end !== -1) src = src.slice(end + 4).replace(/^\r?\n/, "");
  }
  const plain = src
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g, "$1")
    .replace(/[#>*_`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return plain.length > max ? `${plain.slice(0, max)}…` : plain || "(empty note)";
}

export default function MarkdownEditor({
  value,
  onChange,
  mode,
  readOnly,
  notePaths = [],
  getNoteBody,
  onOpenNote,
  jumpHeading,
  jumpBlock,
  slashExtra = [],
}: Props) {
  const pending = useRef(value);
  const previewRef = useRef<HTMLDivElement>(null);
  const [slash, setSlash] = useState<{
    open: boolean;
    query: string;
    from: number;
  } | null>(null);
  const [pagePreview, setPagePreview] = useState<{
    path: string;
    x: number;
    y: number;
    text: string;
  } | null>(null);

  useEffect(() => {
    pending.current = value;
  }, [value]);

  const html = useMemo(() => {
    if (mode === "source") return "";
    return renderMarkdown(value, {
      resolveWikilink: (target) => resolveTarget(target, notePaths),
      getEmbedBody: (target) => {
        const path = resolveTarget(target, notePaths);
        if (!path || !getNoteBody) return null;
        return getNoteBody(path);
      },
    });
  }, [value, mode, notePaths, getNoteBody]);

  useEffect(() => {
    if (!previewRef.current) return;
    if (jumpHeading || jumpBlock) {
      scrollPreviewToTarget(
        previewRef.current,
        jumpHeading ?? undefined,
        jumpBlock ?? undefined,
      );
    }
  }, [html, jumpHeading, jumpBlock]);

  function onPreviewClick(e: React.MouseEvent) {
    const a = (e.target as HTMLElement).closest(
      "a.bf-wikilink",
    ) as HTMLAnchorElement | null;
    if (!a) return;
    e.preventDefault();
    const path = a.dataset.path;
    if (!path) return;
    onOpenNote?.(
      path,
      a.dataset.heading || undefined,
      a.dataset.block || undefined,
    );
  }

  function onPreviewMouseOver(e: React.MouseEvent) {
    const a = (e.target as HTMLElement).closest(
      "a.bf-wikilink",
    ) as HTMLAnchorElement | null;
    if (!a || !a.dataset.path) {
      return;
    }
    const path = a.dataset.path;
    const rect = a.getBoundingClientRect();
    const cached = getNoteBody?.(path);
    if (cached != null) {
      setPagePreview({
        path,
        x: rect.left,
        y: rect.bottom + 6,
        text: stripBodyPreview(cached),
      });
      return;
    }
    setPagePreview({
      path,
      x: rect.left,
      y: rect.bottom + 6,
      text: "Loading…",
    });
    void import("@tauri-apps/api/core").then(({ invoke }) =>
      invoke<string>("read_note", { relativePath: path })
        .then((body) => {
          setPagePreview((prev) =>
            prev && prev.path === path
              ? { ...prev, text: stripBodyPreview(body) }
              : prev,
          );
        })
        .catch(() => {
          setPagePreview((prev) =>
            prev && prev.path === path
              ? { ...prev, text: "Could not load preview" }
              : prev,
          );
        }),
    );
  }

  function onPreviewMouseOut(e: React.MouseEvent) {
    const related = e.relatedTarget as HTMLElement | null;
    if (related?.closest?.(".bf-page-preview")) return;
    if (!(e.target as HTMLElement).closest("a.bf-wikilink")) return;
    setPagePreview(null);
  }

  function applySlash(cmd: SlashCommand) {
    if (cmd.run) {
      cmd.run();
      setSlash(null);
      return;
    }
    if (!cmd.insert || slash == null) return;
    const current = pending.current;
    const before = current.slice(0, slash.from);
    // Remove the "/query" trigger
    const afterSlash = current.slice(slash.from);
    const consumed = afterSlash.match(/^\/[^\s\n]*/);
    const restStart = slash.from + (consumed?.[0].length ?? 1);
    const after = current.slice(restStart);
    const next = `${before}${cmd.insert}${after}`;
    pending.current = next;
    onChange(next);
    setSlash(null);
  }

  function handleChange(v: string) {
    pending.current = v;
    onChange(v);
    // Detect slash command at end of current line
    const m = v.match(/(?:^|\n)\/([^\s\n]*)$/);
    if (m && !readOnly && (mode === "source" || mode === "live")) {
      const from = v.lastIndexOf(`/${m[1]}`);
      setSlash({ open: true, query: m[1] ?? "", from });
    } else {
      setSlash(null);
    }
  }

  const showSource = mode === "source" || mode === "live";
  const showPreview = mode === "live" || mode === "reading";
  const wc = useMemo(() => countWords(value), [value]);

  return (
    <div
      className={`md-workbench mode-${mode}${showSource && showPreview ? " split" : ""}`}
    >
      {showSource ? (
        <div className="cm-host slash-host">
          <CodeMirror
            value={value}
            height="100%"
            theme="dark"
            extensions={[markdown(), theme, EditorView.lineWrapping]}
            editable={!readOnly}
            basicSetup={{
              lineNumbers: true,
              foldGutter: true,
              highlightActiveLine: true,
              bracketMatching: true,
            }}
            onChange={(v: string) => handleChange(v)}
          />
          <SlashMenu
            open={Boolean(slash?.open)}
            query={slash?.query ?? ""}
            extra={slashExtra}
            onPick={applySlash}
            onClose={() => setSlash(null)}
          />
        </div>
      ) : null}
      {showPreview ? (
        <div
          className="md-preview"
          ref={previewRef}
          role="article"
          tabIndex={0}
          onClick={onPreviewClick}
          onMouseOver={onPreviewMouseOver}
          onMouseOut={onPreviewMouseOut}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : null}
      <div className="editor-status-line" aria-live="polite">
        {wc.words} words
      </div>
      {pagePreview ? (
        <div
          className="bf-page-preview"
          style={{ left: pagePreview.x, top: pagePreview.y }}
          role="tooltip"
          onMouseLeave={() => setPagePreview(null)}
        >
          <strong>{pagePreview.path}</strong>
          <p>{pagePreview.text}</p>
        </div>
      ) : null}
    </div>
  );
}
