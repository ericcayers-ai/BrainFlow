import { useMemo } from "react";
import { countWords, extractFootnotes } from "../markdown/renderMarkdown";

type Props = {
  vaultOpen: boolean;
  notePath: string;
  body: string;
};

export default function FootnotesWordCountPanel({ vaultOpen, notePath, body }: Props) {
  const footnotes = useMemo(() => extractFootnotes(body || ""), [body]);
  const counts = useMemo(() => countWords(body || ""), [body]);

  if (!vaultOpen) return null;

  return (
    <div className="footnotes-panel" aria-label="Footnotes and word count">
      <h3>Word count</h3>
      <p className="meta-line">
        {counts.words} words · {counts.characters} chars
        {!notePath ? null : (
          <span className="muted-copy"> · {notePath.split("/").pop()}</span>
        )}
      </p>

      <h3>Footnotes</h3>
      {footnotes.defs.length === 0 && footnotes.refs.length === 0 ? (
        <p className="muted-copy">
          No footnotes. Use <code>[^1]</code> / <code>[^1]: text</code> or{" "}
          <code>^[inline]</code>.
        </p>
      ) : (
        <>
          <div className="link-block">
            <strong>Definitions</strong>
            <ul>
              {footnotes.defs.length === 0 ? (
                <li className="muted-copy">None</li>
              ) : (
                footnotes.defs.map((d) => (
                  <li key={d.id}>
                    <code>[^{d.id}]</code>: {d.body}
                  </li>
                ))
              )}
            </ul>
          </div>
          <div className="link-block">
            <strong>References</strong>
            <ul>
              {footnotes.refs.length === 0 ? (
                <li className="muted-copy">None</li>
              ) : (
                footnotes.refs.map((r, i) => (
                  <li key={`${r.id}-${i}`}>
                    <code>[^{r.id}]</code>{" "}
                    <span className="muted-copy">…{r.preview}…</span>
                  </li>
                ))
              )}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
