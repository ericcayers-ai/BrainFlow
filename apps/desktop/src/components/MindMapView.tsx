import { useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphProjection } from "../graph/model";
import { layoutWithElk } from "../graph/elkLayout";
import { applyLod } from "../graph/lod";

async function layoutRadial(nodes: Node[], edges: Edge[]) {
  const graph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "radial",
      "elk.spacing.nodeNode": "48",
    },
    children: nodes.map((n) => ({ id: n.id, width: 160, height: 48 })),
    edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  };
  const laid = await layoutWithElk(graph);
  return {
    nodes: nodes.map((n) => {
      const ln = laid.children?.find((c) => c.id === n.id);
      return { ...n, position: { x: ln?.x ?? 0, y: ln?.y ?? 0 } };
    }),
    edges,
  };
}

type Props = {
  projection: GraphProjection;
  focusId: string | null;
  onSelect: (id: string) => void;
  pathNodeIds?: string[];
  page?: number;
  onLodMessage?: (msg: string) => void;
};

export default function MindMapView({
  projection,
  focusId,
  onSelect,
  pathNodeIds = [],
  page = 0,
  onLodMessage,
}: Props) {
  const lod = useMemo(
    () =>
      applyLod(projection.nodes, projection.edges, {
        kind: "workflow",
        page,
        focusId,
      }),
    [projection, page, focusId],
  );
  const pathIds = useMemo(() => new Set(pathNodeIds), [pathNodeIds]);

  const initial = useMemo(() => {
    const nodes: Node[] = lod.nodes.map((n, i) => ({
      id: n.id,
      position: { x: i * 40, y: i * 20 },
      data: { label: n.label },
      style: {
        background: focusId === n.id ? "#1f4a36" : pathIds.has(n.id) ? "#243528" : "#152820",
        color: "#e7f2ea",
        border: `1px solid ${focusId === n.id ? "#5ed4a0" : pathIds.has(n.id) ? "#c4a26a" : "#3d7a5c"}`,
        borderRadius: 999,
        padding: 10,
        fontSize: 12,
        width: 160,
      },
    }));
    const edges: Edge[] = lod.edges.map((e) => ({
      id: e.id,
      source: e.from,
      target: e.to,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke:
          pathIds.has(e.from) && pathIds.has(e.to) ? "#e0b35a" : "#6aa88a",
      },
    }));
    return { nodes, edges };
  }, [lod, focusId, pathIds]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  useEffect(() => {
    onLodMessage?.(lod.message);
  }, [lod.message, onLodMessage]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const laid = await layoutRadial(initial.nodes, initial.edges);
        if (!cancelled) {
          setNodes(laid.nodes);
          setEdges(laid.edges);
        }
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
      aria-label="Mind map canvas. Use the Outline panel for keyboard navigation."
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
        <MiniMap pannable zoomable />
        <Controls />
      </ReactFlow>
    </div>
  );
}
