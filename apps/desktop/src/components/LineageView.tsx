import { useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import type { GraphProjection } from "../graph/model";
import { layoutWithElk } from "../graph/elkLayout";

type Props = {
  projection: GraphProjection;
  focusId: string | null;
  onSelect: (id: string) => void;
  pathNodeIds?: string[];
};

export default function LineageView({
  projection,
  focusId,
  onSelect,
  pathNodeIds = [],
}: Props) {
  const pathIds = useMemo(() => new Set(pathNodeIds), [pathNodeIds]);
  const initial = useMemo(() => {
    const nodes: Node[] = projection.nodes.map((n, i) => ({
      id: n.id,
      position: { x: 0, y: i * 70 },
      data: { label: `${n.type}\n${n.label}` },
      style: {
        background: focusId === n.id ? "#243528" : pathIds.has(n.id) ? "#2a2820" : "#101a14",
        color: "#e7f2ea",
        border: `1px solid ${pathIds.has(n.id) ? "#c4a26a" : "#3d7a5c"}`,
        borderRadius: 6,
        padding: 8,
        fontSize: 11,
        whiteSpace: "pre-wrap" as const,
        width: 170,
      },
    }));
    const edges: Edge[] = projection.edges.map((e) => ({
      id: e.id,
      source: e.from,
      target: e.to,
      label: e.type,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke:
          pathIds.has(e.from) && pathIds.has(e.to) ? "#e0b35a" : "#c4a26a",
      },
    }));
    return { nodes, edges };
  }, [projection, focusId, pathIds]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const graph = {
          id: "lineage",
          layoutOptions: {
            "elk.algorithm": "layered",
            "elk.direction": "DOWN",
            "elk.spacing.nodeNode": "36",
          },
          children: initial.nodes.map((n) => ({ id: n.id, width: 170, height: 56 })),
          edges: initial.edges.map((e) => ({
            id: e.id,
            sources: [e.source],
            targets: [e.target],
          })),
        };
        const laid = await layoutWithElk(graph);
        if (cancelled) return;
        setNodes(
          initial.nodes.map((n) => {
            const ln = laid.children?.find((c) => c.id === n.id);
            return { ...n, position: { x: ln?.x ?? 0, y: ln?.y ?? 0 } };
          }),
        );
        setEdges(initial.edges);
      } catch {
        if (!cancelled) {
          setNodes(initial.nodes);
          setEdges(initial.edges);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initial, setNodes, setEdges]);

  return (
    <div
      className="flow-root"
      role="application"
      aria-label="Artifact lineage canvas. Use the Outline panel for keyboard navigation."
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, n) => onSelect(n.id)}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesFocusable
        edgesFocusable
      >
        <Background gap={18} color="#24352c" />
        <Controls />
      </ReactFlow>
    </div>
  );
}
