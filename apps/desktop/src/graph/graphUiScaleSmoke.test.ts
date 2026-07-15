import { test } from "node:test";
import assert from "node:assert/strict";
import { generateWorkflowFixture } from "./fixtures.ts";
import { applyLod, GRAPH_SCALE_LIMITS } from "./lod.ts";
import type { GraphEdge, GraphNode } from "./model.ts";

function nodeIdFromPort(port: string): string {
  return port.split(":")[0] ?? port;
}

/** Mirrors WorkflowGraph toGraphParts for smoke without React DOM. */
function toGraphParts(workflow: ReturnType<typeof generateWorkflowFixture>): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  return {
    nodes: workflow.nodes.map((n) => ({
      id: n.id,
      type: "WorkflowStep" as const,
      label: n.title,
      properties: { ir_type: n.type },
    })),
    edges: (workflow.edges ?? []).map((e) => ({
      id: e.id,
      type: "precedes" as const,
      from: nodeIdFromPort(e.from),
      to: nodeIdFromPort(e.to),
    })),
  };
}

test("graph UI scale smoke: 500 nodes → full LOD → RF-shaped counts", () => {
  const n = GRAPH_SCALE_LIMITS.workflowEditableTarget;
  const wf = generateWorkflowFixture(n);
  assert.equal(wf.nodes.length, n);
  const parts = toGraphParts(wf);
  const lod = applyLod(parts.nodes, parts.edges, {
    kind: "workflow",
    forceMode: "full",
  });
  assert.equal(lod.mode, "full");
  assert.equal(lod.nodes.length, n);
  // React Flow-shaped ids present (smoke without mounting React)
  const rfNodes = lod.nodes.map((node, i) => ({
    id: node.id,
    position: { x: i * 10, y: 0 },
    data: { label: node.label },
  }));
  const rfEdges = lod.edges.map((e) => ({
    id: e.id,
    source: e.from,
    target: e.to,
  }));
  assert.equal(rfNodes.length, n);
  assert.ok(rfEdges.length >= n - 1);
});
