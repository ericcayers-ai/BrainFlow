import assert from "node:assert/strict";
import test from "node:test";
import { applyLod, clusterByDegree, GRAPH_SCALE_LIMITS } from "./lod.ts";
import { collapseGroups } from "./collapse.ts";
import { generateKnowledgeFixture, generateWorkflowFixture } from "./fixtures.ts";
import type { GraphEdge, GraphNode } from "./model.ts";

test("GRAPH_SCALE_LIMITS document Phase 7 targets", () => {
  assert.equal(GRAPH_SCALE_LIMITS.workflowEditableTarget, 500);
  assert.equal(GRAPH_SCALE_LIMITS.knowledgeVisibleTarget, 5000);
});

test("applyLod pages large workflow", () => {
  const wf = generateWorkflowFixture(250);
  const nodes: GraphNode[] = wf.nodes.map((n) => ({
    id: n.id,
    type: "WorkflowStep",
    label: n.title,
  }));
  const edges: GraphEdge[] = wf.edges.map((e) => ({
    id: e.id,
    type: "precedes",
    from: e.from.split(":")[0]!,
    to: e.to.split(":")[0]!,
  }));
  const lod = applyLod(nodes, edges, { kind: "workflow", page: 0 });
  assert.equal(lod.mode, "page");
  assert.ok(lod.nodes.length <= GRAPH_SCALE_LIMITS.workflowVisibleDefault);
  assert.ok(lod.truncated);
});

test("applyLod clusters large knowledge", () => {
  const g = generateKnowledgeFixture(900);
  const lod = applyLod(g.nodes, g.edges, { kind: "knowledge" });
  assert.equal(lod.mode, "cluster");
  assert.ok(lod.nodes.length < g.nodes.length);
});

test("clusterByDegree keeps hubs", () => {
  const nodes: GraphNode[] = Array.from({ length: 20 }, (_, i) => ({
    id: `n${i}`,
    type: "Note",
    label: `n${i}`,
  }));
  const edges: GraphEdge[] = Array.from({ length: 19 }, (_, i) => ({
    id: `e${i}`,
    type: "links_to",
    from: "n0",
    to: `n${i + 1}`,
  }));
  const c = clusterByDegree(nodes, edges, 5);
  assert.ok(c.nodes.some((n) => n.id === "n0"));
  assert.ok(c.nodes.length < nodes.length);
});

test("collapseGroups reduces members", () => {
  const nodes: GraphNode[] = [
    { id: "a", type: "Task", label: "A", properties: { group_id: "g1" } },
    { id: "b", type: "Task", label: "B", properties: { group_id: "g1" } },
    { id: "c", type: "Task", label: "C" },
  ];
  const edges: GraphEdge[] = [
    { id: "e1", type: "precedes", from: "a", to: "b" },
    { id: "e2", type: "precedes", from: "b", to: "c" },
  ];
  const out = collapseGroups(nodes, edges, new Set(["g1"]));
  assert.equal(out.nodes.length, 2);
  assert.ok(out.nodes.some((n) => n.id === "group:g1"));
});
