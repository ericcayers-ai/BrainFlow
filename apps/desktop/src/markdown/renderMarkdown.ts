/**
 * Safe Markdown → HTML for live preview / reading mode.
 * Supports GFM basics, Obsidian callouts, wikilinks, embeds, and KaTeX math.
 */

import { marked, type Tokens } from "marked";
import DOMPurify from "dompurify";
import katex from "katex";

export type PreviewHandlers = {
  resolveWikilink?: (target: StringLike) => string | null;
  getEmbedBody?: (target: string) => string | null;
  onNavigate?: (path: string, heading?: string, block?: string) => void;
};

type StringLike = string;

const CALL_OUT_RE =
  /^>\s*\[!([A-Za-z0-9_-]+)\]([+-]?)\s*(.*)$/;

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function slugify(heading: string): string {
  return heading
    .trim()
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-");
}

function renderMath(tex: string, display: boolean): string {
  try {
    return katex.renderToString(tex, {
      displayMode: display,
      throwOnError: false,
      strict: "ignore",
    });
  } catch {
    return `<code class="math-fallback">${escapeHtml(tex)}</code>`;
  }
}

/** Protect math spans before marked runs. */
function protectMath(src: string): { text: string; slots: string[] } {
  const slots: string[] = [];
  let text = src.replace(/\$\$([\s\S]+?)\$\$/g, (_, tex: string) => {
    const i = slots.length;
    slots.push(renderMath(tex.trim(), true));
    return `\u0000MATH${i}\u0000`;
  });
  text = text.replace(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g, (_, tex: string) => {
    const i = slots.length;
    slots.push(renderMath(tex.trim(), false));
    return `\u0000MATH${i}\u0000`;
  });
  return { text, slots };
}

function restoreMath(html: string, slots: string[]): string {
  return html.replace(/\u0000MATH(\d+)\u0000/g, (_, n: string) => slots[Number(n)] ?? "");
}

function transformFootnotes(src: string): {
  text: string;
  slots: string[];
  footnotes: { id: string; body: string }[];
} {
  const slots: string[] = [];
  const defs = new Map<string, string>();
  const lines = src.split("\n");
  const kept: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const m = lines[i].match(/^\[\^([^\]]+)\]:\s*(.*)$/);
    if (!m) {
      kept.push(lines[i]);
      i += 1;
      continue;
    }
    const id = m[1].trim();
    const bodyParts = [m[2] ?? ""];
    i += 1;
    while (i < lines.length && (/^\s{2,}\S/.test(lines[i]) || lines[i].startsWith("\t"))) {
      bodyParts.push(lines[i].replace(/^\s+/, ""));
      i += 1;
    }
    defs.set(id, bodyParts.join("\n").trim());
  }

  let text = kept.join("\n");
  let inlineIdx = 0;
  text = text.replace(/\^\[([^\]]+)\]/g, (_, body: string) => {
    inlineIdx += 1;
    const id = `inline-${inlineIdx}`;
    defs.set(id, body.trim());
    return `[^${id}]`;
  });

  text = text.replace(/\[\^([^\]]+)\]/g, (_, id: string) => {
    const safe = escapeHtml(id);
    if (!defs.has(id)) {
      const html = `<sup class="bf-footnote-ref missing" title="Missing footnote">[^${safe}]</sup>`;
      const n = slots.length;
      slots.push(html);
      return `\u0000FN${n}\u0000`;
    }
    const html = `<sup class="bf-footnote-ref"><a href="#fn-${safe}" id="fnref-${safe}" data-footnote="${safe}">${safe}</a></sup>`;
    const n = slots.length;
    slots.push(html);
    return `\u0000FN${n}\u0000`;
  });

  const footnotes = [...defs.entries()].map(([id, body]) => ({ id, body }));
  if (footnotes.length) {
    const section = [
      `<section class="bf-footnotes" aria-label="Footnotes"><hr /><ol>`,
      ...footnotes.map((f) => {
        const safe = escapeHtml(f.id);
        return `<li id="fn-${safe}"><span class="bf-fn-body">${escapeHtml(f.body)}</span> <a class="bf-fn-back" href="#fnref-${safe}" aria-label="Back to reference">↩</a></li>`;
      }),
      `</ol></section>`,
    ].join("");
    const n = slots.length;
    slots.push(section);
    text = `${text}\n\n\u0000FN${n}\u0000\n`;
  }

  return { text, slots, footnotes };
}

function restoreSlots(html: string, slots: string[], prefix: string): string {
  const re = new RegExp(`\\u0000${prefix}(\\d+)\\u0000`, "g");
  return html.replace(re, (_, n: string) => slots[Number(n)] ?? "");
}

/** Extract footnote definitions and references for the Footnotes view. */
export function extractFootnotes(source: string): {
  refs: { id: string; preview: string }[];
  defs: { id: string; body: string }[];
} {
  let src = source.replace(/^\uFEFF/, "");
  if (src.startsWith("---")) {
    const end = src.indexOf("\n---", 3);
    if (end !== -1) src = src.slice(end + 4).replace(/^\r?\n/, "");
  }
  const defs = new Map<string, string>();
  const lines = src.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^\[\^([^\]]+)\]:\s*(.*)$/);
    if (!m) continue;
    const id = m[1].trim();
    const bodyParts = [m[2] ?? ""];
    let j = i + 1;
    while (j < lines.length && (/^\s{2,}\S/.test(lines[j]) || lines[j].startsWith("\t"))) {
      bodyParts.push(lines[j].replace(/^\s+/, ""));
      j += 1;
    }
    defs.set(id, bodyParts.join(" ").trim());
  }
  const refs: { id: string; preview: string }[] = [];
  const refRe = /\[\^([^\]]+)\]/g;
  let rm: RegExpExecArray | null;
  while ((rm = refRe.exec(src)) !== null) {
    const lineStart = src.lastIndexOf("\n", rm.index) + 1;
    const nextNl = src.indexOf("\n", rm.index);
    const line = src.slice(lineStart, nextNl === -1 ? src.length : nextNl);
    if (/^\[\^[^\]]+\]:/.test(line.trim())) continue;
    const id = rm[1];
    const preview = src
      .slice(Math.max(0, rm.index - 24), rm.index + rm[0].length + 24)
      .replace(/\s+/g, " ");
    refs.push({ id, preview });
  }
  const inlineRe = /\^\[([^\]]+)\]/g;
  while ((rm = inlineRe.exec(src)) !== null) {
    refs.push({ id: "(inline)", preview: rm[1] });
  }
  return {
    refs,
    defs: [...defs.entries()].map(([id, body]) => ({ id, body })),
  };
}

export function countWords(source: string): {
  words: number;
  characters: number;
  charactersNoSpaces: number;
} {
  let src = source.replace(/^\uFEFF/, "");
  if (src.startsWith("---")) {
    const end = src.indexOf("\n---", 3);
    if (end !== -1) src = src.slice(end + 4).replace(/^\r?\n/, "");
  }
  const words = src.split(/\s+/).filter((w) => w.length > 0).length;
  const characters = src.length;
  const charactersNoSpaces = src.replace(/\s/g, "").length;
  return { words, characters, charactersNoSpaces };
}

function transformCallouts(src: string): string {
  const lines = src.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const m = lines[i].match(CALL_OUT_RE);
    if (!m) {
      out.push(lines[i]);
      i += 1;
      continue;
    }
    const kind = m[1].toLowerCase();
    const title = m[3]?.trim() || kind.charAt(0).toUpperCase() + kind.slice(1);
    const body: string[] = [];
    i += 1;
    while (i < lines.length && lines[i].startsWith(">")) {
      body.push(lines[i].replace(/^>\s?/, ""));
      i += 1;
    }
    out.push(
      `<aside class="bf-callout bf-callout-${escapeHtml(kind)}" data-callout="${escapeHtml(kind)}"><div class="bf-callout-title">${escapeHtml(title)}</div><div class="bf-callout-body">\n\n${body.join("\n")}\n\n</div></aside>`,
    );
  }
  return out.join("\n");
}

function parseWikiInner(inner: string): {
  target: string;
  alias?: string;
  heading?: string;
  block?: string;
} {
  const [targetPart, alias] = inner.includes("|")
    ? [inner.slice(0, inner.indexOf("|")).trim(), inner.slice(inner.indexOf("|") + 1).trim()]
    : [inner.trim(), undefined];
  let target = targetPart;
  let heading: string | undefined;
  let block: string | undefined;
  if (targetPart.includes("#")) {
    const [t, rest] = targetPart.split("#", 2);
    target = t.trim();
    if (rest.startsWith("^")) {
      block = rest.slice(1).trim();
    } else if (rest.includes("#^")) {
      const [h, b] = rest.split("#^", 2);
      heading = h.trim();
      block = b.trim();
    } else {
      heading = rest.trim();
    }
  }
  return { target, alias, heading, block };
}

function transformWikilinksAndEmbeds(
  src: string,
  handlers: PreviewHandlers,
): string {
  // Embeds first
  let text = src.replace(/!\[\[([^\[\]]+)\]\]/g, (_, inner: string) => {
    const { target, heading, block } = parseWikiInner(inner);
    const body = handlers.getEmbedBody?.(target);
    if (!body) {
      return `<div class="bf-embed bf-embed-missing" data-target="${escapeHtml(target)}">Missing embed: ${escapeHtml(target)}</div>`;
    }
    let excerpt = body;
    if (heading) {
      const re = new RegExp(
        `(^|\\n)#+\\s+${heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\n([\\s\\S]*?)(?=\\n#+\\s|$)`,
        "i",
      );
      const hm = excerpt.match(re);
      if (hm) excerpt = hm[2] ?? excerpt;
    }
    if (block) {
      const re = new RegExp(`([\\s\\S]*?\\^${block.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`);
      const bm = excerpt.match(re);
      if (bm) excerpt = bm[1] ?? excerpt;
    }
    // Nested render without further embeds to avoid infinite recursion
    const nested = renderMarkdown(excerpt, { ...handlers, getEmbedBody: undefined }, true);
    return `<div class="bf-embed" data-target="${escapeHtml(target)}">${nested}</div>`;
  });

  text = text.replace(/\[\[([^\[\]]+)\]\]/g, (_, inner: string) => {
    const { target, alias, heading, block } = parseWikiInner(inner);
    const label = alias || [target, heading, block ? `^${block}` : ""]
      .filter(Boolean)
      .join(heading || block ? " › " : "");
    const resolved = handlers.resolveWikilink?.(target) ?? null;
    const href = resolved
      ? `#note/${encodeURIComponent(resolved)}${heading ? `#h/${encodeURIComponent(heading)}` : ""}${block ? `#b/${encodeURIComponent(block)}` : ""}`
      : `#unresolved/${encodeURIComponent(target)}`;
    const cls = resolved ? "bf-wikilink" : "bf-wikilink unresolved";
    return `<a class="${cls}" href="${href}" data-path="${escapeHtml(resolved ?? "")}" data-heading="${escapeHtml(heading ?? "")}" data-block="${escapeHtml(block ?? "")}">${escapeHtml(label)}</a>`;
  });

  return text;
}

function addHeadingIds(html: string): string {
  return html.replace(/<h([1-6])>([\s\S]*?)<\/h\1>/gi, (_, level: string, inner: string) => {
    const plain = inner.replace(/<[^>]+>/g, "").trim();
    const id = slugify(plain);
    return `<h${level} id="h-${id}">${inner}</h${level}>`;
  });
}

function markBlockIds(html: string): string {
  // Paragraph or list item ending with ^block-id
  return html.replace(
    /(<(?:p|li)[^>]*>)([\s\S]*?)\^([A-Za-z0-9_-]+)\s*(<\/(?:p|li)>)/gi,
    (_, open: string, body: string, id: string, close: string) =>
      `${open}<span id="b-${escapeHtml(id)}" class="bf-block-id">${body}</span>${close}`,
  );
}

const PURIFY: DOMPurify.Config = {
  ALLOWED_TAGS: [
    "a",
    "abbr",
    "aside",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
    "section",
    "ol",
    "sup",
    "del",
    "input",
  ],
  ALLOWED_ATTR: [
    "href",
    "class",
    "id",
    "data-path",
    "data-heading",
    "data-block",
    "data-callout",
    "data-target",
    "data-footnote",
    "alt",
    "title",
    "checked",
    "disabled",
    "type",
    "aria-hidden",
    "aria-label",
    "style",
  ],
  ALLOW_DATA_ATTR: true,
  // Block javascript: and data: (except images handled by omit)
  ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|#):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
};

/**
 * Convert Markdown to sanitized HTML.
 * @param skipFrontmatter strip YAML frontmatter when true (default).
 */
export function renderMarkdown(
  source: string,
  handlers: PreviewHandlers = {},
  nested = false,
): string {
  let src = source.replace(/^\uFEFF/, "");
  if (!nested && src.startsWith("---")) {
    const end = src.indexOf("\n---", 3);
    if (end !== -1) {
      src = src.slice(end + 4).replace(/^\r?\n/, "");
    }
  }

  src = transformCallouts(src);
  const { text: fnProtected, slots: fnSlots } = transformFootnotes(src);
  const { text: mathProtected, slots: mathSlots } = protectMath(fnProtected);
  const withLinks = transformWikilinksAndEmbeds(mathProtected, handlers);

  marked.setOptions({ gfm: true, breaks: false });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const renderer = new marked.Renderer() as any;
  const prevLink = renderer.link?.bind(renderer);
  renderer.link = (token: Tokens.Link | string, title?: string, text?: string) => {
    // marked v15 uses token object; tolerate both
    if (typeof token === "object" && token && "href" in token) {
      const href = String(token.href ?? "");
      if (/^\s*javascript:/i.test(href) || /^\s*data:/i.test(href)) {
        return escapeHtml(token.text ?? "");
      }
    } else if (typeof token === "string") {
      if (/^\s*javascript:/i.test(token) || /^\s*data:/i.test(token)) {
        return escapeHtml(text ?? "");
      }
    }
    if (prevLink) {
      if (typeof token === "object") return prevLink(token);
      return prevLink(token, title, text);
    }
    return `<a href="${escapeHtml(String(token))}">${text ?? ""}</a>`;
  };

  let html = marked.parse(withLinks, { renderer }) as string;
  html = restoreMath(html, mathSlots);
  html = restoreSlots(html, fnSlots, "FN");
  html = addHeadingIds(html);
  html = markBlockIds(html);
  return DOMPurify.sanitize(html, PURIFY as Parameters<typeof DOMPurify.sanitize>[1]);
}

export function scrollPreviewToTarget(
  root: HTMLElement,
  heading?: string,
  block?: string,
): void {
  if (block) {
    const el = root.querySelector(`#b-${CSS.escape(block)}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
  }
  if (heading) {
    const id = `h-${slugify(heading)}`;
    const el = root.querySelector(`#${CSS.escape(id)}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

export { slugify };
