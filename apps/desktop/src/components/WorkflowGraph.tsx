import { useEffect, useMemo, useState } from "react";
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
import type { WorkflowIr } from "../types";
import { layoutWithElk } from "../graph/elkLayout";
import { applyLod, GRAPH_SCALE_LIMITS } from "../graph/lod";
import type { GraphEdge, GraphNode } from "../graph/model";

function nodeIdFromPort(port: string): string {
  return port.split(":")[0] ?? port;
}

async function layout(
  nodes: Node[],
  edges: Edge[],
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  const graph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.spacing.nodeNode": "40",
      "elk.layered.spacing.nodeNodeBetweenLayers": "64",
    },
    children: nodes.map((n) => ({
      id: n.id,
      width: 180,
      height: 56,
    })),
    edges: edges.map((e) => ({
      id: e.id,
      sources: [e.source],
      targets: [e.target],
    })),
  };
  const laid = await layoutWithElk(graph);
  const positioned = nodes.map((n) => {
    const ln = laid.children?.find((c) => c.id === n.id);
    return {
      ...n,
      position: { x: ln?.x ?? 0, y: ln?.y ?? 0 },
    };
  });
  return { nodes: positioned, edges };
}

function toGraphParts(workflow: WorkflowIr | null): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  if (!workflow?.nodes?.length) return { nodes: [], edges: [] };
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
  focusId: string | null,
  nodeStatuses: Record<string, string> | undefined,
  pathIds: Set<string>,
): { nodes: Node[]; edges: Edge[] } {
  if (!graphNodes.length) {
    return {
      nodes: [
        {
          id: "placeholder",
          position: { x: 0, y: 0 },
          data: { label: "Generate a workflow to render the DAG" },
          style: {
            background: "#1a2a24",
            color: "#c5d4cc",
            border: "1px solid #2f4a3d",
            borderRadius: 8,
            padding: 12,
            width: 280,
          },
        },
      ],
      edges: [],
    };
  }
  const nodes: Node[] = graphNodes.map((n, i) => {
    const status = nodeStatuses?.[n.id];
    const focused = focusId === n.id;
    const onPath = pathIds.has(n.id);
    return {
      id: n.id,
      position: { x: i * 200, y: 0 },
      data: {
        label: `${n.label}\n(${String(n.properties?.ir_type ?? n.type)})${status ? `\n[${status}]` : ""}`,
      },
      style: {
        background: focused ? "#1f4a36" : onPath ? "#243528" : "#143028",
        color: "#e7f2ea",
        border: `1px solid ${focused ? "#5ed4a0" : onPath ? "#c4a26a" : "#3d7a5c"}`,
        borderRadius: 8,
        padding: 10,
        fontSize: 12,
        whiteSpace: "pre-wrap",
        width: 180,
      },
    };
  });
  const edges: Edge[] = graphEdges.map((e) => {
    const onPath = pathIds.has(e.from) && pathIds.has(e.to);
    return {
      id: e.id,
      source: e.from,
      target: e.to,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: onPath ? "#e0b35a" : "#6aa88a", strokeWidth: onPath ? 2.5 : 1.5 },
    };
  });
  return { nodes, edges };
}

type Props = {
  workflow: WorkflowIr | null;
  focusId?: string | null;
  onSelect?: (id: string) => void;
  nodeStatuses?: Record<string, string>;
  /** Highlight node ids on a traced path */
  pathNodeIds?: string[];
  page?: number;
  onLodMessage?: (msg: string) => void;
};

export default function WorkflowGraph({
  workflow,
  focusId = null,
  onSelect,
  nodeStatuses,
  pathNodeIds = [],
  page = 0,
  onLodMessage,
}: Props) {
  const parts = useMemo(() => toGraphParts(workflow), [workflow]);
  const lod = useMemo(
    () =>
      applyLod(parts.nodes, parts.edges, {
        kind: "workflow",
        page,
        focusId,
        forceMode:
          parts.nodes.length <= GRAPH_SCALE_LIMITS.workflowFullLayoutSoft
            ? "full"
            : undefined,
      }),
    [parts, page, focusId],
  );
  const pathIds = useMemo(() => new Set(pathNodeIds), [pathNodeIds]);

  const initial = useMemo(
    () => toFlow(lod.nodes, lod.edges, focusId, nodeStatuses, pathIds),
    [lod, focusId, nodeStatuses, pathIds],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [layoutError, setLayoutError] = useState("");
  const [layoutStatus, setLayoutStatus] = useState("");

  useEffect(() => {
    onLodMessage?.(lod.message);
  }, [lod.message, onLodMessage]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mapped = toFlow(lod.nodes, lod.edges, focusId, nodeStatuses, pathIds);
        setLayoutStatus(
          lod.nodes.length > 80 ? "Computing ELK layout in worker…" : "",
        );
        const laid = await layout(mapped.nodes, mapped.edges);
        if (!cancelled) {
          setNodes(laid.nodes);
          setEdges(laid.edges);
          setLayoutError("");
          setLayoutStatus("");
        }
      } catch (e) {
        if (!cancelled) {
          setLayoutError(String(e));
          setLayoutStatus("");
          const mapped = toFlow(lod.nodes, lod.edges, focusId, nodeStatuses, pathIds);
          setNodes(mapped.nodes);
          setEdges(mapped.edges);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lod, focusId, nodeStatuses, pathIds, setNodes, setEdges]);

  return (
    <div
      className="flow-root"
      role="application"
      aria-label="Workflow DAG canvas. Use the Outline panel for keyboard navigation."
    >
      {layoutError ? <p className="warn">Layout fallback: {layoutError}</p> : null}
      {layoutStatus ? (
        <p className="suite-live" role="status" aria-live="polite">
          {layoutStatus}
        </p>
      ) : null}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, n) => onSelect?.(n.id)}
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
