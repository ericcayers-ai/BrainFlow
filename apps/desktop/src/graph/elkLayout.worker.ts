/**
 * Dedicated ELK layout Web Worker (Vite: `new Worker(new URL(...), { type: "module" })`).
 * Keeps layered/radial layout off the UI thread for Workflow DAG / mind map.
 */
import ELK from "elkjs/lib/elk.bundled.js";

const elk = new ELK();

export type ElkLayoutRequest = {
  id: number;
  graph: unknown;
};

export type ElkLayoutResponse =
  | { id: number; ok: true; result: unknown }
  | { id: number; ok: false; error: string };

self.onmessage = async (ev: MessageEvent<ElkLayoutRequest>) => {
  const { id, graph } = ev.data;
  try {
    const result = await elk.layout(graph);
    const msg: ElkLayoutResponse = { id, ok: true, result };
    self.postMessage(msg);
  } catch (e) {
    const msg: ElkLayoutResponse = { id, ok: false, error: String(e) };
    self.postMessage(msg);
  }
};
