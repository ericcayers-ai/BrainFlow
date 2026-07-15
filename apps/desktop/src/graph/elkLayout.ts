import type { ElkLayoutResponse } from "./elkLayout.worker";

export type ElkLaidOut = {
  children?: Array<{ id: string; x?: number; y?: number; width?: number; height?: number }>;
};

type Pending = {
  resolve: (v: ElkLaidOut) => void;
  reject: (e: Error) => void;
};

let worker: Worker | null = null;
let nextId = 1;
const pending = new Map<number, Pending>();
let workerFailed = false;

function getWorker(): Worker | null {
  if (workerFailed) return null;
  if (typeof Worker === "undefined") return null;
  if (!worker) {
    try {
      worker = new Worker(new URL("./elkLayout.worker.ts", import.meta.url), {
        type: "module",
      });
      worker.onmessage = (ev: MessageEvent<ElkLayoutResponse>) => {
        const msg = ev.data;
        const slot = pending.get(msg.id);
        if (!slot) return;
        pending.delete(msg.id);
        if (msg.ok) slot.resolve(msg.result as ElkLaidOut);
        else slot.reject(new Error(msg.error));
      };
      worker.onerror = () => {
        workerFailed = true;
        for (const [, slot] of pending) {
          slot.reject(new Error("ELK worker error"));
        }
        pending.clear();
        worker?.terminate();
        worker = null;
      };
    } catch {
      workerFailed = true;
      return null;
    }
  }
  return worker;
}

/** Main-thread ELK fallback (tests / Node stress / worker unavailable). */
export async function layoutWithElkMain(graph: unknown): Promise<ElkLaidOut> {
  const { default: ELK } = await import("elkjs/lib/elk.bundled.js");
  const elk = new ELK();
  return elk.layout(graph) as Promise<ElkLaidOut>;
}

/**
 * Prefer Web Worker layout; fall back to main-thread ELK if workers are unavailable.
 */
export async function layoutWithElk(graph: unknown): Promise<ElkLaidOut> {
  const w = getWorker();
  if (!w) return layoutWithElkMain(graph);
  return new Promise<ElkLaidOut>((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    w.postMessage({ id, graph });
  });
}

export function terminateElkWorker(): void {
  worker?.terminate();
  worker = null;
  pending.clear();
}
