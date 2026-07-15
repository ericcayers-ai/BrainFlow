/**
 * Offline stress harness for Phase 7 graph scale (no DOM / no worker).
 * Run: npm run stress:graph -w desktop
 */
import { performance } from "node:perf_hooks";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { generateKnowledgeFixture, generateWorkflowFixture } from "../src/graph/fixtures.ts";
import { graphFromWorkflow } from "../src/graph/model.ts";
import { applyLod, GRAPH_SCALE_LIMITS } from "../src/graph/lod.ts";
import { shortestPath } from "../src/graph/pathTracing.ts";
import { layoutWithElkMain } from "../src/graph/elkLayout.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "../../..");

function ms(start: number): number {
  return Math.round((performance.now() - start) * 100) / 100;
}

async function main() {
  const results: Record<string, unknown> = {
    measured_at: new Date().toISOString(),
    platform: process.platform,
    node: process.version,
    limits: GRAPH_SCALE_LIMITS,
  };

  {
    const t0 = performance.now();
    const wf = generateWorkflowFixture(500);
    const genMs = ms(t0);
    const t1 = performance.now();
    const g = graphFromWorkflow(wf);
    const mapMs = ms(t1);
    const t2 = performance.now();
    const lod = applyLod(
      g.nodes.filter((n) => n.type === "WorkflowStep" || n.type === "Goal"),
      g.edges,
      { kind: "workflow", forceMode: "full" },
    );
    const lodMs = ms(t2);
    const layoutNodes = lod.nodes.map((n) => ({ id: n.id, width: 180, height: 56 }));
    const layoutEdges = lod.edges.map((e) => ({
      id: e.id,
      sources: [e.from],
      targets: [e.to],
    }));
    const t3 = performance.now();
    await layoutWithElkMain({
      id: "stress-500",
      layoutOptions: {
        "elk.algorithm": "layered",
        "elk.direction": "RIGHT",
      },
      children: layoutNodes,
      edges: layoutEdges,
    });
    const layoutMs = ms(t3);
    const mid = g.nodes[Math.floor(g.nodes.length / 2)]!.id;
    const path = shortestPath(g.edges, g.nodes[0]!.id, mid);
    results.workflow_500 = {
      nodes: wf.nodes.length,
      graph_nodes: g.nodes.length,
      edges: g.edges.length,
      generate_ms: genMs,
      graphFromWorkflow_ms: mapMs,
      lod_ms: lodMs,
      elk_main_thread_layout_ms: layoutMs,
      path_found: path.found,
      path_len: path.nodeIds.length,
      note: "ELK measured on main thread (Node); production uses Web Worker",
    };
  }

  {
    const t0 = performance.now();
    const kg = generateKnowledgeFixture(5000);
    const genMs = ms(t0);
    const t1 = performance.now();
    const lod = applyLod(kg.nodes, kg.edges, { kind: "knowledge" });
    const lodMs = ms(t1);
    const t2 = performance.now();
    const path = shortestPath(
      kg.edges,
      kg.nodes[0]!.id,
      kg.nodes[Math.min(2500, kg.nodes.length - 1)]!.id,
    );
    const pathMs = ms(t2);
    results.knowledge_5000 = {
      nodes: kg.nodes.length,
      edges: kg.edges.length,
      generate_ms: genMs,
      lod_mode: lod.mode,
      lod_visible_nodes: lod.nodes.length,
      lod_ms: lodMs,
      path_ms: pathMs,
      path_found: path.found,
      path_len: path.nodeIds.length,
    };
  }

  {
    const kg = generateKnowledgeFixture(5000);
    const t0 = performance.now();
    const page = applyLod(kg.nodes, kg.edges, {
      kind: "knowledge",
      forceMode: "page",
      page: 0,
    });
    results.knowledge_5000_page = {
      mode: page.mode,
      visible: page.nodes.length,
      page_count: page.pageCount,
      ms: ms(t0),
    };
  }

  const outDir = join(root, "docs", "spikes");
  mkdirSync(outDir, { recursive: true });
  const jsonPath = join(outDir, "graph-scale-results.json");
  writeFileSync(jsonPath, JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
  console.log(`\nWrote ${jsonPath}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
