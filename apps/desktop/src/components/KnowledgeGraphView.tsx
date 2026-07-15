import { useEffect, useMemo, useRef } from "react";
import cytoscape from "cytoscape";
import type { GraphProjection } from "../graph/model";
import { applyLod } from "../graph/lod";

type Props = {
  projection: GraphProjection;
  focusId: string | null;
  onSelect: (id: string) => void;
  pathNodeIds?: string[];
  page?: number;
  onLodMessage?: (msg: string) => void;
};

/** Cytoscape knowledge / relationship exploration (ADR 0003) with LOD for large graphs. */
export default function KnowledgeGraphView({
  projection,
  focusId,
  onSelect,
  pathNodeIds = [],
  page = 0,
  onLodMessage,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const lod = useMemo(
    () =>
      applyLod(projection.nodes, projection.edges, {
        kind: "knowledge",
        page,
        focusId,
      }),
    [projection, page, focusId],
  );
  const pathIds = useMemo(() => new Set(pathNodeIds), [pathNodeIds]);

  useEffect(() => {
    onLodMessage?.(lod.message);
  }, [lod.message, onLodMessage]);

  useEffect(() => {
    if (!host.current) return;
    const cy = cytoscape({
      container: host.current,
      elements: [
        ...lod.nodes.map((n) => ({
          data: { id: n.id, label: n.label, type: n.type },
        })),
        ...lod.edges.map((e) => ({
          data: { id: e.id, source: e.from, target: e.to, label: e.type },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": "#1d4a35",
            color: "#e7f2ea",
            "font-size": "10px",
            "text-wrap": "wrap",
            "text-max-width": "80px",
            width: "28px",
            height: "28px",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#4a7a60",
            "target-arrow-color": "#4a7a60",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
        {
          selector: ".focused",
          style: {
            "background-color": "#3dbf7a",
            "border-width": 2,
            "border-color": "#9dd9b4",
          },
        },
        {
          selector: ".on-path",
          style: {
            "background-color": "#c4a26a",
            "border-width": 2,
            "border-color": "#e0b35a",
          },
        },
        {
          selector: "edge.on-path",
          style: {
            width: 3,
            "line-color": "#e0b35a",
            "target-arrow-color": "#e0b35a",
          },
        },
      ],
      layout: { name: "cose", animate: false, padding: 24 },
    });
    cy.on("tap", "node", (evt) => {
      onSelect(evt.target.id());
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [lod, onSelect]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass("focused");
    cy.elements().removeClass("on-path");
    if (focusId) cy.getElementById(focusId).addClass("focused");
    for (const id of pathIds) {
      cy.getElementById(id).addClass("on-path");
    }
  }, [focusId, pathIds, lod]);

  return (
    <div
      className="cyto-root"
      ref={host}
      role="application"
      aria-label="Knowledge graph canvas. Use the Outline panel for keyboard navigation."
      tabIndex={0}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && focusId) {
          e.preventDefault();
          onSelect(focusId);
        }
      }}
    />
  );
}
