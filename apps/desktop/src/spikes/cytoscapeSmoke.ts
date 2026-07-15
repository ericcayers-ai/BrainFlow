/**
 * Cytoscape import smoke — dense knowledge graph engine (ADR 0003).
 * Not wired into the Workflow Suite UI yet; confirms the dependency loads.
 */
import cytoscape from "cytoscape";

export function cytoscapeSmoke(): number {
  const cy = cytoscape({
    headless: true,
    elements: [
      { data: { id: "a" } },
      { data: { id: "b" } },
      { data: { id: "ab", source: "a", target: "b" } },
    ],
  });
  const n = cy.nodes().length;
  cy.destroy();
  return n;
}
