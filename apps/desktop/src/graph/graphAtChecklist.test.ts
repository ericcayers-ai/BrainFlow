/**
 * Automated coverage for docs/ACCESSIBILITY.md §6.1 (graph keyboard / focus).
 * Does NOT claim NVDA / VoiceOver sign-off — those remain manual (steps 7).
 */

import assert from "node:assert/strict";
import test from "node:test";
import {
  announceOutlineActivate,
  announceOutlineSelection,
  announcePathStatus,
  assertSingleTabStop,
  GRAPH_AT_VIEWS,
  isCanvasLeaveKey,
  outlineAccessibleName,
  outlineIdsForView,
  outlinesInSync,
  runOutlineKeySequence,
} from "./graphAtModel.ts";
import { graphFromWorkflow, project } from "./model.ts";
import { generateWorkflowFixture } from "./fixtures.ts";
import { parseGraphPatch } from "./patchValidate.ts";
import { shortestPath } from "./pathTracing.ts";

const sampleWorkflow = {
  workflow_id: "wf-at",
  goal: { statement: "AT checklist" },
  nodes: [
    { id: "aaaaaaaa-0000-4000-8000-000000000001", type: "summarize", title: "Summarize" },
    { id: "aaaaaaaa-0000-4000-8000-000000000002", type: "transform", title: "Transform" },
    { id: "aaaaaaaa-0000-4000-8000-000000000003", type: "write_artifact", title: "Write" },
  ],
  edges: [
    {
      id: "eeeeeeee-0000-4000-8000-000000000001",
      from: "aaaaaaaa-0000-4000-8000-000000000001:out",
      to: "aaaaaaaa-0000-4000-8000-000000000002:in",
      kind: "data",
    },
    {
      id: "eeeeeeee-0000-4000-8000-000000000002",
      from: "aaaaaaaa-0000-4000-8000-000000000002:out",
      to: "aaaaaaaa-0000-4000-8000-000000000003:in",
      kind: "data",
    },
  ],
};

test("§6.1 step2: single roving tab stop in outline", () => {
  const g = graphFromWorkflow(sampleWorkflow);
  const outline = project(g, "workflow_dag").outline;
  assert.ok(outline.length >= 2);
  const focus = outline[1]!.id;
  const check = assertSingleTabStop(outline, focus);
  assert.equal(check.ok, true);
  const bad = assertSingleTabStop(outline, "missing-id-forces-default");
  // missing focus falls back to index 0 → still exactly one tab stop
  assert.equal(bad.ok, true);
});

test("§6.1 step3: Arrow/Home/End move focus + announce", () => {
  const g = graphFromWorkflow(sampleWorkflow);
  const outline = project(g, "workflow_dag").outline;
  const end = runOutlineKeySequence(outline, outline[0]!.id, ["End"]);
  assert.equal(end, outline[outline.length - 1]!.id);
  const home = runOutlineKeySequence(outline, end, ["Home"]);
  assert.equal(home, outline[0]!.id);
  const down = runOutlineKeySequence(outline, home, ["ArrowDown", "ArrowDown"]);
  assert.equal(down, outline[Math.min(2, outline.length - 1)]!.id);
  const ann = announceOutlineSelection(outline, down);
  assert.ok(ann);
  assert.match(ann!.text, /of/);
  assert.equal(ann!.politeness, "polite");
});

test("§6.1 step4: Enter activate announce is assertive", () => {
  const g = graphFromWorkflow(sampleWorkflow);
  const item = project(g, "workflow_dag").outline[0]!;
  const ann = announceOutlineActivate(item);
  assert.equal(ann.politeness, "assertive");
  assert.match(ann.text, /Selected/);
  assert.equal(outlineAccessibleName(item), `${item.node_type}: ${item.label}`);
});

test("§6.1 step5: path status announce", () => {
  const g = graphFromWorkflow(sampleWorkflow);
  const a = g.nodes[0]!.id;
  const c = g.nodes[2]!.id;
  const path = shortestPath(g.edges, a, c);
  assert.equal(path.found, true);
  const ok = announcePathStatus(path, a, c);
  assert.match(ok.text, /Path/);
  const miss = announcePathStatus(
    { found: false, nodeIds: [], edgeIds: [] },
    a,
    "missing",
  );
  assert.match(miss.text, /No path/);
});

test("§6.1 step6: outline twin stays present across views", () => {
  const g = graphFromWorkflow(sampleWorkflow);
  // Expand with knowledge nodes so every view has content
  const rich = {
    ...g,
    nodes: [
      ...g.nodes,
      { id: "aaaaaaaa-0000-4000-8000-000000000010", type: "Note" as const, label: "Note" },
      { id: "aaaaaaaa-0000-4000-8000-000000000011", type: "File" as const, label: "File" },
      { id: "aaaaaaaa-0000-4000-8000-000000000012", type: "Evidence" as const, label: "Ev" },
    ],
  };
  for (const view of GRAPH_AT_VIEWS) {
    const proj = project(rich, view);
    assert.ok(proj.outline.length >= 1, `outline empty for ${view}`);
    assert.ok(outlineIdsForView(proj.outline).length === proj.outline.length);
  }
  const a = project(rich, "workflow_dag").outline;
  const b = project(rich, "workflow_dag").outline;
  assert.equal(outlinesInSync(a, b), true);
});

test("§6.1 step7 model: Escape/Tab leave canvas application", () => {
  assert.equal(isCanvasLeaveKey("Escape"), true);
  assert.equal(isCanvasLeaveKey("Tab"), true);
  assert.equal(isCanvasLeaveKey("ArrowDown"), false);
});

test("§6.1 step8: invalid AI patch surfaces error; valid parses", () => {
  const bad = parseGraphPatch({ schema_version: 1, ops: [{ op: "explode" }] });
  assert.equal(bad.ok, false);
  const good = parseGraphPatch({
    schema_version: 1,
    ops: [
      {
        op: "add_node",
        node: {
          id: "bbbbbbbb-0000-4000-8000-000000000099",
          type: "Note",
          label: "Patched",
        },
      },
    ],
  });
  assert.equal(good.ok, true);
});

test("§6.1 stress outline: 50-node workflow remains keyboard-navigable in model", () => {
  const wf = generateWorkflowFixture(50);
  const g = graphFromWorkflow(wf);
  const outline = project(g, "workflow_dag").outline;
  assert.ok(outline.length >= 10);
  let focus: string | null = outline[0]!.id;
  focus = runOutlineKeySequence(outline, focus, ["End", "Home", "ArrowDown", "ArrowDown"]);
  assert.ok(focus);
  assert.equal(assertSingleTabStop(outline, focus).ok, true);
});
