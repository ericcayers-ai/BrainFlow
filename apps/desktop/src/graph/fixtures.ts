import type { CanonicalGraph, GraphEdge, GraphNode } from "./model";
import type { WorkflowIr } from "../types";

function uuidFromIndex(i: number, namespace: number): string {
  const hex = (i + 1).toString(16).padStart(12, "0");
  return `${namespace.toString(16).padStart(8, "0")}-0000-4000-8000-${hex}`;
}

/** Stress fixture: ~N workflow IR nodes in a layered DAG. */
export function generateWorkflowFixture(nodeCount = 500): WorkflowIr {
  const nodes = Array.from({ length: nodeCount }, (_, i) => ({
    id: uuidFromIndex(i, 1),
    type: i % 5 === 0 ? "summarize" : "transform",
    title: `Step ${i + 1}`,
    permission_class: "safe_overlay",
  }));
  const edges = [];
  for (let i = 1; i < nodeCount; i++) {
    const parent = Math.floor((i - 1) / 2);
    edges.push({
      id: uuidFromIndex(i, 2),
      from: `${nodes[parent]!.id}:out`,
      to: `${nodes[i]!.id}:in`,
      kind: "data",
    });
  }
  return {
    schema_version: 1,
    workflow_id: uuidFromIndex(0, 9),
    title: `Stress workflow ${nodeCount}`,
    goal: { statement: `Layout stress ${nodeCount} nodes` },
    nodes,
    edges,
  };
}

/** Stress fixture: ~N relationship nodes for knowledge / Cytoscape explore. */
export function generateKnowledgeFixture(nodeCount = 5000): CanonicalGraph {
  const nodes: GraphNode[] = Array.from({ length: nodeCount }, (_, i) => ({
    id: uuidFromIndex(i, 3),
    type: (["Note", "Entity", "Evidence", "Question", "File"] as const)[i % 5]!,
    label: `Rel ${i + 1}`,
    properties: i % 40 === 0 ? { group_id: `g${Math.floor(i / 40)}` } : {},
  }));
  const edges: GraphEdge[] = [];
  for (let i = 1; i < nodeCount; i++) {
    const parent = i % Math.max(1, Math.floor(i / 3) || 1);
    edges.push({
      id: uuidFromIndex(i, 4),
      type: (["links_to", "mentions", "supports", "derived_from"] as const)[i % 4]!,
      from: nodes[parent]!.id,
      to: nodes[i]!.id,
    });
    if (i % 17 === 0 && i > 10) {
      edges.push({
        id: uuidFromIndex(i + nodeCount, 4),
        type: "mentions",
        from: nodes[i]!.id,
        to: nodes[i - 7]!.id,
      });
    }
  }
  return {
    schema_version: 1,
    graph_id: uuidFromIndex(0, 8),
    nodes,
    edges,
    views: [{ id: "stress-knowledge", kind: "knowledge", layout: "cose" }],
  };
}
