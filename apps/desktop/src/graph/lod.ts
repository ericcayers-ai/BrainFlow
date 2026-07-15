import type { GraphEdge, GraphNode } from "./model";

/**
 * Documented interactive caps for graph canvases.
 * Soft limits trigger LOD/pagination; hard max is a hard fail-closed render budget.
 */
export const GRAPH_SCALE_LIMITS = {
  /** Target editable workflow DAG (Phase 7 exit) */
  workflowEditableTarget: 500,
  /** Full ELK layout without progressive pagination */
  workflowFullLayoutSoft: 500,
  /** Visible workflow nodes before page/cluster */
  workflowVisibleDefault: 200,
  /** Knowledge / relationship explore soft cluster threshold */
  knowledgeClusterAbove: 800,
  /** Phase 7 relationship-node target */
  knowledgeVisibleTarget: 5000,
  /** Cytoscape hard cap per viewport page */
  knowledgePageSize: 400,
  /** Absolute elements (nodes+edges) before refuse-to-full-render */
  absoluteRenderHardMax: 12_000,
} as const;

export type LodMode = "full" | "page" | "cluster";

export type LodResult = {
  mode: LodMode;
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** Cluster aggregate nodes (synthetic) when mode === "cluster" */
  page: number;
  pageCount: number;
  truncated: boolean;
  message: string;
};

function pageSlice(
  nodes: GraphNode[],
  edges: GraphEdge[],
  page: number,
  pageSize: number,
): { nodes: GraphNode[]; edges: GraphEdge[]; pageCount: number } {
  const pageCount = Math.max(1, Math.ceil(nodes.length / pageSize));
  const p = Math.min(Math.max(0, page), pageCount - 1);
  const slice = nodes.slice(p * pageSize, p * pageSize + pageSize);
  const ids = new Set(slice.map((n) => n.id));
  const e = edges.filter((ed) => ids.has(ed.from) && ids.has(ed.to));
  return { nodes: slice, edges: e, pageCount };
}

/** Degree-based clustering: keep top hubs + sample, collapse the rest into synthetic clusters. */
export function clusterByDegree(
  nodes: GraphNode[],
  edges: GraphEdge[],
  keepHubs: number,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const degree = new Map<string, number>();
  for (const n of nodes) degree.set(n.id, 0);
  for (const e of edges) {
    degree.set(e.from, (degree.get(e.from) ?? 0) + 1);
    degree.set(e.to, (degree.get(e.to) ?? 0) + 1);
  }
  const ranked = [...nodes].sort(
    (a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0),
  );
  const hubs = ranked.slice(0, keepHubs);
  const hubIds = new Set(hubs.map((n) => n.id));
  const leftover = ranked.slice(keepHubs);
  const bucketCount = Math.min(12, Math.max(1, Math.ceil(leftover.length / 50)));
  const clusters: GraphNode[] = [];
  for (let i = 0; i < bucketCount; i++) {
    const members = leftover.filter((_, idx) => idx % bucketCount === i);
    if (!members.length) continue;
    clusters.push({
      id: `cluster-${i}`,
      type: "Entity",
      label: `Cluster ${i + 1} (${members.length})`,
      properties: {
        synthetic: true,
        member_ids: members.map((m) => m.id),
        member_count: members.length,
      },
    });
  }
  const outNodes = [...hubs, ...clusters];
  const clusterOf = new Map<string, string>();
  for (const c of clusters) {
    const members = (c.properties?.member_ids as string[]) ?? [];
    for (const id of members) clusterOf.set(id, c.id);
  }
  const mapId = (id: string) => (hubIds.has(id) ? id : (clusterOf.get(id) ?? id));
  const edgeKey = new Set<string>();
  const outEdges: GraphEdge[] = [];
  for (const e of edges) {
    const from = mapId(e.from);
    const to = mapId(e.to);
    if (from === to) continue;
    const key = `${from}->${to}:${e.type}`;
    if (edgeKey.has(key)) continue;
    edgeKey.add(key);
    outEdges.push({
      id: `agg-${edgeKey.size}`,
      type: e.type,
      from,
      to,
      properties: { aggregated: true },
    });
  }
  return { nodes: outNodes, edges: outEdges };
}

/**
 * Apply LOD / pagination so large graphs stay interactive.
 * Prefer focus neighborhood when `focusId` is set.
 */
export function applyLod(
  nodes: GraphNode[],
  edges: GraphEdge[],
  opts: {
    kind: "workflow" | "knowledge";
    page?: number;
    focusId?: string | null;
    forceMode?: LodMode;
  },
): LodResult {
  const page = opts.page ?? 0;
  const soft =
    opts.kind === "workflow"
      ? GRAPH_SCALE_LIMITS.workflowVisibleDefault
      : GRAPH_SCALE_LIMITS.knowledgePageSize;
  const clusterAbove =
    opts.kind === "knowledge"
      ? GRAPH_SCALE_LIMITS.knowledgeClusterAbove
      : GRAPH_SCALE_LIMITS.workflowFullLayoutSoft;

  if (opts.forceMode === "full" || nodes.length <= soft) {
    return {
      mode: "full",
      nodes,
      edges,
      page: 0,
      pageCount: 1,
      truncated: false,
      message: `Full graph (${nodes.length} nodes)`,
    };
  }

  if (opts.focusId) {
    const neigh = new Set<string>([opts.focusId]);
    for (const e of edges) {
      if (e.from === opts.focusId) neigh.add(e.to);
      if (e.to === opts.focusId) neigh.add(e.from);
    }
    // 2-hop soft expand capped
    for (const e of edges) {
      if (neigh.has(e.from) && neigh.size < soft) neigh.add(e.to);
      if (neigh.has(e.to) && neigh.size < soft) neigh.add(e.from);
    }
    const n = nodes.filter((x) => neigh.has(x.id));
    const ids = new Set(n.map((x) => x.id));
    const e = edges.filter((ed) => ids.has(ed.from) && ids.has(ed.to));
    return {
      mode: "page",
      nodes: n,
      edges: e,
      page: 0,
      pageCount: 1,
      truncated: n.length < nodes.length,
      message: `Neighborhood of focus (${n.length}/${nodes.length} nodes)`,
    };
  }

  if (
    opts.forceMode !== "page" &&
    (opts.forceMode === "cluster" ||
      (opts.kind === "knowledge" && nodes.length > clusterAbove))
  ) {
    const clustered = clusterByDegree(nodes, edges, Math.min(soft, 120));
    return {
      mode: "cluster",
      nodes: clustered.nodes,
      edges: clustered.edges,
      page: 0,
      pageCount: 1,
      truncated: true,
      message: `Clustered ${nodes.length} → ${clustered.nodes.length} nodes (expand via outline)`,
    };
  }

  const sliced = pageSlice(nodes, edges, page, soft);
  return {
    mode: "page",
    nodes: sliced.nodes,
    edges: sliced.edges,
    page: Math.min(page, sliced.pageCount - 1),
    pageCount: sliced.pageCount,
    truncated: sliced.pageCount > 1,
    message: `Page ${Math.min(page, sliced.pageCount - 1) + 1}/${sliced.pageCount} (${sliced.nodes.length} of ${nodes.length} nodes)`,
  };
}
