import type { GraphEdge } from "./model";

export type PathTrace = {
  found: boolean;
  nodeIds: string[];
  edgeIds: string[];
};

/**
 * Shortest path (unweighted BFS) between two node ids on directed edges.
 * Also tries reverse orientation if forward search fails (undirected explore).
 */
export function shortestPath(
  edges: GraphEdge[],
  fromId: string,
  toId: string,
): PathTrace {
  if (fromId === toId) {
    return { found: true, nodeIds: [fromId], edgeIds: [] };
  }

  const tryBfs = (directed: boolean): PathTrace | null => {
    const adj = new Map<string, { to: string; edgeId: string }[]>();
    for (const e of edges) {
      const list = adj.get(e.from) ?? [];
      list.push({ to: e.to, edgeId: e.id });
      adj.set(e.from, list);
      if (!directed) {
        const back = adj.get(e.to) ?? [];
        back.push({ to: e.from, edgeId: e.id });
        adj.set(e.to, back);
      }
    }
    const q: string[] = [fromId];
    const prev = new Map<string, { via: string; edgeId: string }>();
    const seen = new Set<string>([fromId]);
    while (q.length) {
      const cur = q.shift()!;
      for (const step of adj.get(cur) ?? []) {
        if (seen.has(step.to)) continue;
        seen.add(step.to);
        prev.set(step.to, { via: cur, edgeId: step.edgeId });
        if (step.to === toId) {
          const nodeIds: string[] = [toId];
          const edgeIds: string[] = [];
          let walk = toId;
          while (walk !== fromId) {
            const p = prev.get(walk)!;
            edgeIds.push(p.edgeId);
            nodeIds.push(p.via);
            walk = p.via;
          }
          nodeIds.reverse();
          edgeIds.reverse();
          return { found: true, nodeIds, edgeIds };
        }
        q.push(step.to);
      }
    }
    return null;
  };

  return (
    tryBfs(true) ??
    tryBfs(false) ?? { found: false, nodeIds: [], edgeIds: [] }
  );
}
