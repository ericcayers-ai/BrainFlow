/**
 * TypeScript projections of the canonical graph (mirrors crates/graph).
 * Views never own divergent truth — patches must validate before apply.
 */

export type NodeType =
  | "File"
  | "Note"
  | "Block"
  | "Entity"
  | "Goal"
  | "Constraint"
  | "Task"
  | "Decision"
  | "Question"
  | "Evidence"
  | "Artifact"
  | "WorkflowStep"
  | "Person";

export type EdgeType =
  | "links_to"
  | "derived_from"
  | "supports"
  | "contradicts"
  | "depends_on"
  | "produces"
  | "assigned_to"
  | "precedes"
  | "mentions";

export type ViewKind =
  | "workflow_dag"
  | "mind_map"
  | "tree_outline"
  | "knowledge"
  | "lineage";

export type GraphNode = {
  id: string;
  type: NodeType;
  label: string;
  properties?: Record<string, unknown>;
  locators?: string[];
  provenance?: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  type: EdgeType;
  from: string;
  to: string;
  properties?: Record<string, unknown>;
  weight?: number;
  provenance?: Record<string, unknown>;
};

export type CanonicalGraph = {
  schema_version: 1;
  graph_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  views?: { id: string; kind: ViewKind; layout?: string }[];
};

export type OutlineItem = {
  id: string;
  label: string;
  node_type: string;
  depth: number;
  children: string[];
};

export type GraphProjection = {
  schema_version: 1;
  view: ViewKind;
  nodes: GraphNode[];
  edges: GraphEdge[];
  outline: OutlineItem[];
};

export type GraphDiff = {
  nodes_added: string[];
  nodes_removed: string[];
  nodes_changed: string[];
  edges_added: string[];
  edges_removed: string[];
  edges_changed: string[];
};

export type GraphPatchOp =
  | { op: "add_node"; node: GraphNode }
  | { op: "remove_node"; id: string }
  | { op: "update_node"; id: string; label?: string; properties?: Record<string, unknown> }
  | { op: "add_edge"; edge: GraphEdge }
  | { op: "remove_edge"; id: string };

export type GraphPatch = {
  schema_version: 1;
  summary?: string;
  ops: GraphPatchOp[];
};

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "00000000-0000-4000-8000-000000000000";
}

function portId(port: string): string {
  return port.split(":")[0] ?? port;
}

/** Build canonical graph from workflow IR. */
export function graphFromWorkflow(workflow: {
  workflow_id?: string;
  goal?: { statement?: string };
  nodes?: { id: string; type: string; title: string; permission_class?: string }[];
  edges?: { id: string; from: string; to: string; kind: string }[];
}): CanonicalGraph {
  const goalId = newId();
  const nodes: GraphNode[] = [
    {
      id: goalId,
      type: "Goal",
      label: workflow.goal?.statement || "Goal",
      properties: {},
    },
  ];
  const idMap = new Map<string, string>();
  for (const n of workflow.nodes ?? []) {
    idMap.set(n.id, n.id);
    nodes.push({
      id: n.id,
      type: "WorkflowStep",
      label: n.title,
      properties: { ir_type: n.type, permission_class: n.permission_class },
    });
  }
  const edges: GraphEdge[] = [];
  const first = (workflow.nodes ?? [])[0];
  if (first) {
    edges.push({
      id: newId(),
      type: "precedes",
      from: goalId,
      to: first.id,
    });
  }
  for (const e of workflow.edges ?? []) {
    const from = portId(e.from);
    const to = portId(e.to);
    if (idMap.has(from) && idMap.has(to)) {
      edges.push({
        id: e.id || newId(),
        type: "precedes",
        from,
        to,
      });
    }
  }
  return {
    schema_version: 1,
    graph_id: workflow.workflow_id || newId(),
    nodes,
    edges,
    views: [{ id: "default-dag", kind: "workflow_dag", layout: "layered" }],
  };
}

function buildOutline(nodes: GraphNode[], edges: GraphEdge[]): OutlineItem[] {
  const children = new Map<string, string[]>();
  const indeg = new Map<string, number>();
  for (const n of nodes) indeg.set(n.id, 0);
  for (const e of edges) {
    const list = children.get(e.from) ?? [];
    list.push(e.to);
    children.set(e.from, list);
    indeg.set(e.to, (indeg.get(e.to) ?? 0) + 1);
  }
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const roots = [...indeg.entries()].filter(([, d]) => d === 0).map(([id]) => id);
  const out: OutlineItem[] = [];
  const seen = new Set<string>();
  const q: { id: string; depth: number }[] = roots.map((id) => ({ id, depth: 0 }));
  while (q.length) {
    const { id, depth } = q.shift()!;
    if (seen.has(id)) continue;
    seen.add(id);
    const n = byId.get(id);
    if (!n) continue;
    const kids = children.get(id) ?? [];
    out.push({
      id,
      label: n.label,
      node_type: n.type,
      depth,
      children: kids,
    });
    for (const k of kids) q.push({ id: k, depth: depth + 1 });
  }
  for (const n of nodes) {
    if (!seen.has(n.id)) {
      out.push({
        id: n.id,
        label: n.label,
        node_type: n.type,
        depth: 0,
        children: [],
      });
    }
  }
  return out;
}

function filterProjection(
  graph: CanonicalGraph,
  view: ViewKind,
  nodePred: (n: GraphNode) => boolean,
  edgePred: (e: GraphEdge) => boolean,
): GraphProjection {
  const nodes = graph.nodes.filter(nodePred);
  const ids = new Set(nodes.map((n) => n.id));
  const edges = graph.edges.filter(
    (e) => ids.has(e.from) && ids.has(e.to) && edgePred(e),
  );
  return {
    schema_version: 1,
    view,
    nodes,
    edges,
    outline: buildOutline(nodes, edges),
  };
}

export function project(graph: CanonicalGraph, view: ViewKind): GraphProjection {
  switch (view) {
    case "workflow_dag":
      return filterProjection(
        graph,
        view,
        (n) => n.type === "WorkflowStep" || n.type === "Task" || n.type === "Goal",
        (e) => e.type === "precedes" || e.type === "depends_on",
      );
    case "mind_map":
    case "tree_outline":
      return filterProjection(
        graph,
        view,
        (n) =>
          ["Goal", "Question", "Entity", "Task", "Note"].includes(n.type),
        () => true,
      );
    case "lineage":
      return filterProjection(
        graph,
        view,
        (n) =>
          ["File", "Evidence", "WorkflowStep", "Artifact", "Note"].includes(n.type),
        (e) =>
          e.type === "derived_from" || e.type === "produces" || e.type === "supports",
      );
    case "knowledge":
    default:
      return filterProjection(graph, "knowledge", () => true, () => true);
  }
}

export function diffGraphs(a: CanonicalGraph, b: CanonicalGraph): GraphDiff {
  const aN = new Map(a.nodes.map((n) => [n.id, n]));
  const bN = new Map(b.nodes.map((n) => [n.id, n]));
  const aE = new Map(a.edges.map((e) => [e.id, e]));
  const bE = new Map(b.edges.map((e) => [e.id, e]));
  const diff: GraphDiff = {
    nodes_added: [...bN.keys()].filter((id) => !aN.has(id)),
    nodes_removed: [...aN.keys()].filter((id) => !bN.has(id)),
    nodes_changed: [],
    edges_added: [...bE.keys()].filter((id) => !aE.has(id)),
    edges_removed: [...aE.keys()].filter((id) => !bE.has(id)),
    edges_changed: [],
  };
  for (const id of aN.keys()) {
    if (!bN.has(id)) continue;
    const x = aN.get(id)!;
    const y = bN.get(id)!;
    if (x.label !== y.label || x.type !== y.type) diff.nodes_changed.push(id);
  }
  for (const id of aE.keys()) {
    if (!bE.has(id)) continue;
    const x = aE.get(id)!;
    const y = bE.get(id)!;
    if (x.from !== y.from || x.to !== y.to || x.type !== y.type) diff.edges_changed.push(id);
  }
  return diff;
}

/**
 * Apply a patch that has already passed schema validation (`parseGraphPatch`).
 * Still enforces structural invariants (duplicates, dangling edges).
 */
export function applyGraphPatch(
  graph: CanonicalGraph,
  patch: GraphPatch,
): { ok: true; graph: CanonicalGraph } | { ok: false; error: string } {
  if (patch.schema_version !== 1) {
    return { ok: false, error: "unsupported patch schema_version" };
  }
  if (!Array.isArray(patch.ops) || patch.ops.length > 50) {
    return { ok: false, error: "patch ops missing or exceeds bound 50" };
  }
  const next: CanonicalGraph = {
    ...graph,
    nodes: [...graph.nodes],
    edges: [...graph.edges],
  };
  for (const op of patch.ops) {
    switch (op.op) {
      case "add_node":
        if (next.nodes.some((n) => n.id === op.node.id)) {
          return { ok: false, error: `duplicate node ${op.node.id}` };
        }
        next.nodes.push(op.node);
        break;
      case "remove_node":
        next.nodes = next.nodes.filter((n) => n.id !== op.id);
        next.edges = next.edges.filter((e) => e.from !== op.id && e.to !== op.id);
        break;
      case "update_node": {
        const n = next.nodes.find((x) => x.id === op.id);
        if (!n) return { ok: false, error: `missing node ${op.id}` };
        if (op.label !== undefined) n.label = op.label;
        if (op.properties) n.properties = { ...n.properties, ...op.properties };
        break;
      }
      case "add_edge":
        next.edges.push(op.edge);
        break;
      case "remove_edge":
        next.edges = next.edges.filter((e) => e.id !== op.id);
        break;
      default:
        return { ok: false, error: "unknown patch op" };
    }
  }
  const ids = new Set(next.nodes.map((n) => n.id));
  for (const e of next.edges) {
    if (!ids.has(e.from) || !ids.has(e.to)) {
      return { ok: false, error: `dangling edge ${e.id}` };
    }
  }
  return { ok: true, graph: next };
}
