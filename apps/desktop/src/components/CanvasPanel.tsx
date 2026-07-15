import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

type CanvasNode = {
  id: string;
  type: string;
  x: number;
  y: number;
  width: number;
  height: number;
  text?: string | null;
  file?: string | null;
  color?: string | null;
};

type CanvasEdge = {
  id: string;
  from_node: string;
  to_node: string;
  label?: string | null;
};

type CanvasDoc = {
  schema_version: number;
  kind: string;
  id: string;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  note?: string | null;
};

type CanvasListItem = { path: string; id: string; title: string };

type Props = {
  vaultOpen: boolean;
  onOpenNote?: (path: string) => void;
  refreshKey: number;
};

export default function CanvasPanel({ vaultOpen, onOpenNote, refreshKey }: Props) {
  const [list, setList] = useState<CanvasListItem[]>([]);
  const [path, setPath] = useState("");
  const [doc, setDoc] = useState<CanvasDoc | null>(null);
  const [error, setError] = useState("");
  const [pan, setPan] = useState({ x: 40, y: 40 });
  const drag = useRef<{
    id: string;
    ox: number;
    oy: number;
    nx: number;
    ny: number;
  } | null>(null);
  const surface = useRef<HTMLDivElement>(null);

  const loadList = useCallback(async () => {
    if (!vaultOpen) {
      setList([]);
      return;
    }
    try {
      const items = await invoke<CanvasListItem[]>("list_canvases");
      setList(items);
      if (!path && items[0]) setPath(items[0].path);
    } catch (e) {
      setError(String(e));
    }
  }, [vaultOpen, path]);

  const loadDoc = useCallback(async (rel: string) => {
    if (!rel) {
      setDoc(null);
      return;
    }
    try {
      const d = await invoke<CanvasDoc>("read_canvas", { relativePath: rel });
      setDoc(d);
      setError("");
    } catch (e) {
      setError(String(e));
      setDoc(null);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList, refreshKey]);

  useEffect(() => {
    if (path) void loadDoc(path);
  }, [path, loadDoc, refreshKey]);

  async function persist(next: CanvasDoc) {
    setDoc(next);
    if (!path) return;
    try {
      await invoke("write_canvas", { relativePath: path, document: next });
    } catch (e) {
      setError(String(e));
    }
  }

  function onPointerDown(e: React.PointerEvent, node: CanvasNode) {
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = {
      id: node.id,
      ox: e.clientX,
      oy: e.clientY,
      nx: node.x,
      ny: node.y,
    };
  }

  function onPointerMove(e: React.PointerEvent) {
    const d = drag.current;
    if (!d || !doc) return;
    const dx = e.clientX - d.ox;
    const dy = e.clientY - d.oy;
    const nextNodes = doc.nodes.map((n) =>
      n.id === d.id ? { ...n, x: d.nx + dx, y: d.ny + dy } : n,
    );
    setDoc({ ...doc, nodes: nextNodes });
  }

  async function onPointerUp() {
    const d = drag.current;
    drag.current = null;
    if (!d || !doc) return;
    await persist(doc);
  }

  async function addTextNode() {
    if (!doc) return;
    const id = `n${Date.now()}`;
    const node: CanvasNode = {
      id,
      type: "text",
      x: 80 - pan.x,
      y: 80 - pan.y,
      width: 220,
      height: 100,
      text: "New card",
    };
    await persist({ ...doc, nodes: [...doc.nodes, node] });
  }

  if (!vaultOpen) {
    return <p className="muted-copy">Open a vault to edit canvases.</p>;
  }

  return (
    <div className="canvas-panel" aria-label="Canvas board">
      <div className="canvas-toolbar">
        <label className="field inline">
          <span>Canvas</span>
          <select value={path} onChange={(e) => setPath(e.target.value)}>
            {list.map((c) => (
              <option key={c.path} value={c.path}>
                {c.title || c.id}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => void addTextNode()} disabled={!doc}>
          Add card
        </button>
        <button
          type="button"
          className="ghost"
          onClick={() => setPan({ x: 40, y: 40 })}
        >
          Reset view
        </button>
      </div>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div
        className="canvas-surface"
        ref={surface}
        onPointerMove={onPointerMove}
        onPointerUp={() => void onPointerUp()}
        style={{
          backgroundPosition: `${pan.x}px ${pan.y}px`,
        }}
      >
        <div
          className="canvas-world"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px)` }}
        >
          {doc?.edges.map((e) => {
            const from = doc.nodes.find((n) => n.id === e.from_node);
            const to = doc.nodes.find((n) => n.id === e.to_node);
            if (!from || !to) return null;
            const x1 = from.x + from.width / 2;
            const y1 = from.y + from.height / 2;
            const x2 = to.x + to.width / 2;
            const y2 = to.y + to.height / 2;
            return (
              <svg
                key={e.id}
                className="canvas-edge"
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  overflow: "visible",
                  width: 1,
                  height: 1,
                  pointerEvents: "none",
                }}
              >
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke="var(--line)"
                  strokeWidth={2}
                />
              </svg>
            );
          })}
          {doc?.nodes.map((n) => (
            <div
              key={n.id}
              className="canvas-node"
              style={{
                left: n.x,
                top: n.y,
                width: n.width,
                height: n.height,
              }}
              onPointerDown={(e) => onPointerDown(e, n)}
            >
              {n.file ? (
                <button
                  type="button"
                  className="linkish"
                  onClick={() => onOpenNote?.(n.file!)}
                >
                  {n.file}
                </button>
              ) : (
                <div className="canvas-node-text">{n.text ?? n.id}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
