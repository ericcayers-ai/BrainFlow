import assert from "node:assert/strict";
import test from "node:test";
import { shortestPath } from "./pathTracing.ts";
import type { GraphEdge } from "./model.ts";

const edges: GraphEdge[] = [
  { id: "e1", type: "precedes", from: "a", to: "b" },
  { id: "e2", type: "precedes", from: "b", to: "c" },
  { id: "e3", type: "precedes", from: "a", to: "d" },
];

test("shortestPath finds directed path", () => {
  const p = shortestPath(edges, "a", "c");
  assert.equal(p.found, true);
  assert.deepEqual(p.nodeIds, ["a", "b", "c"]);
  assert.deepEqual(p.edgeIds, ["e1", "e2"]);
});

test("shortestPath same node", () => {
  const p = shortestPath(edges, "a", "a");
  assert.equal(p.found, true);
  assert.deepEqual(p.nodeIds, ["a"]);
});

test("shortestPath undirected fallback", () => {
  const p = shortestPath(edges, "c", "a");
  assert.equal(p.found, true);
  assert.ok(p.nodeIds.includes("a") && p.nodeIds.includes("c"));
});

test("shortestPath missing", () => {
  const p = shortestPath(edges, "a", "z");
  assert.equal(p.found, false);
});
