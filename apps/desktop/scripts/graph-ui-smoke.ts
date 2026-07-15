/**
 * React Flow data-prep smoke for Phase 7 scale (500 editable workflow nodes).
 * Node harness — no Puppeteer/Playwright, no NVDA claim.
 *
 * Mirrors WorkflowGraph toGraphParts → LOD → toFlow conversion path and times it.
 * Run: npm run smoke:graph-ui -w desktop
 */
import { performance } from "node:perf_hooks";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { MarkerType, type Edge, type Node } from "@xyflow/react";
import { generateWorkflowFixture } from "../src/graph/fixtures.ts";
import { applyLod, GRAPH_SCALE_LIMITS } from "../src/graph/lod.ts";
import type { GraphEdge, GraphNode } from "../src/graph/model.ts";
import { layoutWithElkMain } from "../src/graph/elkLayout.ts";
import type { WorkflowIr } from "../src/types.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "../../..");

/** Soft budgets for data-prep smoke (not mid-tier GPU pan/zoom). */
const BUDGETS = {
  /** toFlow + LOD for 500 nodes */
  flowPrepP95Ms: 100,
  /** Full ELK often >500ms — progress UI expected; record only */
  elkWarnMs: 500,
  nodes: GRAPH_SCALE_LIMITS.workflowEditableTarget,
};

function ms(start: number): number {
  return Math.round((performance.now() - start) * 100) / 100;
}

function nodeIdFromPort(port: string): string {
  return port.split(":")[0] ?? port;
}

function toGraphParts(workflow: WorkflowIr): { nodes: GraphNode[]; edges: GraphEdge[] } {
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

function toFlow(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[],
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graphNodes.map((n, i) => ({
    id: n.id,
    position: { x: (i % 20) * 200, y: Math.floor(i / 20) * 80 },
    data: { label: `${n.label}\n(${String(n.properties?.ir_type ?? n.type)})` },
    style: {
      background: "#143028",
      color: "#e7f2ea",
      border: "1px solid #3d7a5c",
      borderRadius: 8,
      padding: 10,
      fontSize: 12,
      width: 180,
    },
  }));
  const edges: Edge[] = graphEdges.map((e) => ({
    id: e.id,
    source: e.from,
    target: e.to,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { stroke: "#6aa88a", strokeWidth: 1.5 },
  }));
  return { nodes, edges };
}

function percentile(sorted: number[], p: number): number {
  if (!sorted.length) return 0;
  const rank = Math.round((p / 100) * (sorted.length - 1));
  return sorted[Math.min(rank, sorted.length - 1)]!;
}

async function main() {
  const n = BUDGETS.nodes;
  const prepSamples: number[] = [];
  let lastFlow = { nodes: [] as Node[], edges: [] as Edge[] };
  let lodMode = "full";

  for (let r = 0; r < 12; r++) {
    const t0 = performance.now();
    const wf = generateWorkflowFixture(n);
    const parts = toGraphParts(wf);
    const lod = applyLod(parts.nodes, parts.edges, {
      kind: "workflow",
      forceMode: parts.nodes.length <= GRAPH_SCALE_LIMITS.workflowFullLayoutSoft ? "full" : undefined,
    });
    lodMode = lod.mode;
    lastFlow = toFlow(lod.nodes, lod.edges);
    // Simulate light interaction: focus remap + edge recount (React Flow prop churn)
    const focusId = lastFlow.nodes[Math.floor(lastFlow.nodes.length / 2)]?.id;
    const focused = lastFlow.nodes.map((node) =>
      node.id === focusId
        ? { ...node, style: { ...node.style, border: "1px solid #5ed4a0" } }
        : node,
    );
    if (focused.length !== n && lod.mode === "full") {
      throw new Error(`expected ${n} React Flow nodes in full LOD, got ${focused.length}`);
    }
    prepSamples.push(ms(t0));
  }

  prepSamples.sort((a, b) => a - b);
  const prepP50 = percentile(prepSamples, 50);
  const prepP95 = percentile(prepSamples, 95);

  const layoutNodes = lastFlow.nodes.map((node) => ({
    id: node.id,
    width: 180,
    height: 56,
  }));
  const layoutEdges = lastFlow.edges.map((e) => ({
    id: e.id,
    sources: [e.source],
    targets: [e.target],
  }));
  const tLayout = performance.now();
  await layoutWithElkMain({
    id: "ui-smoke-500",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
    },
    children: layoutNodes,
    edges: layoutEdges,
  });
  const elkMs = ms(tLayout);

  const prepOk = prepP95 <= BUDGETS.flowPrepP95Ms;
  const results = {
    measured_at: new Date().toISOString(),
    platform: process.platform,
    node: process.version,
    kind: "react_flow_data_prep_smoke",
    target_nodes: n,
    lod_mode: lodMode,
    react_flow_nodes: lastFlow.nodes.length,
    react_flow_edges: lastFlow.edges.length,
    prep_p50_ms: prepP50,
    prep_p95_ms: prepP95,
    elk_main_thread_ms: elkMs,
    budgets: BUDGETS,
    prep_budget_ok: prepOk,
    elk_needs_progress_ui: elkMs > BUDGETS.elkWarnMs,
    nvda_claimed: false,
    note:
      "Node harness mirrors WorkflowGraph conversion + LOD + React Flow node/edge shapes. " +
      "Not a browser pan/zoom mid-tier GPU soak; not NVDA/AT sign-off.",
  };

  const outDir = join(root, "docs", "spikes");
  mkdirSync(outDir, { recursive: true });
  const jsonPath = join(outDir, "graph-ui-smoke-results.json");
  writeFileSync(jsonPath, JSON.stringify(results, null, 2) + "\n");

  console.log(JSON.stringify(results, null, 2));
  console.log(`\nWrote ${jsonPath}`);
  if (!prepOk) {
    console.error(`FAIL: prep p95 ${prepP95}ms > budget ${BUDGETS.flowPrepP95Ms}ms`);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
