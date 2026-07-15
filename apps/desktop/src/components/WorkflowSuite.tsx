import { useCallback, useEffect, useId, useMemo, useState } from "react";
import type { OutlineItem, ViewKind } from "../graph/model";
import {
  applyGraphPatch,
  diffGraphs,
  graphFromWorkflow,
  project,
  type CanonicalGraph,
  type GraphPatch,
} from "../graph/model";
import { parseGraphPatch } from "../graph/patchValidate";
import { shortestPath } from "../graph/pathTracing";
import { collapseGroups, discoverGroups } from "../graph/collapse";
import type { WorkflowIr } from "../types";
import WorkflowGraph from "./WorkflowGraph";
import MindMapView from "./MindMapView";
import TreeOutlineView from "./TreeOutlineView";
import KnowledgeGraphView from "./KnowledgeGraphView";
import LineageView from "./LineageView";
import GraphOutline from "./GraphOutline";
import GraphDiffPanel from "./GraphDiffPanel";

const VIEWS: { id: ViewKind; label: string }[] = [
  { id: "workflow_dag", label: "Workflow DAG" },
  { id: "mind_map", label: "Mind map" },
  { id: "tree_outline", label: "Tree / outline" },
  { id: "knowledge", label: "Knowledge" },
  { id: "lineage", label: "Lineage" },
];

type Props = {
  workflow: WorkflowIr | null;
  /** Optional prior workflow version for diff. */
  previousWorkflow?: WorkflowIr | null;
  liveMessage?: string;
};

export default function WorkflowSuite({
  workflow,
  previousWorkflow = null,
  liveMessage = "",
}: Props) {
  const [view, setView] = useState<ViewKind>("workflow_dag");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [pathAnchorId, setPathAnchorId] = useState<string | null>(null);
  const [pendingPatch, setPendingPatch] = useState<GraphPatch | null>(null);
  const [patchError, setPatchError] = useState("");
  const [lodMessage, setLodMessage] = useState("");
  const [page, setPage] = useState(0);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(
    () => new Set(),
  );
  const liveId = useId();

  const graph = useMemo(
    () => (workflow ? graphFromWorkflow(workflow) : null),
    [workflow],
  );
  const [overlayGraph, setOverlayGraph] = useState<CanonicalGraph | null>(null);
  useEffect(() => {
    setOverlayGraph(null);
    setPendingPatch(null);
    setPatchError("");
    setPage(0);
    setPathAnchorId(null);
    setCollapsedGroups(new Set());
  }, [workflow?.workflow_id]);

  const active = overlayGraph ?? graph;

  const groups = useMemo(
    () => (active ? discoverGroups(active.nodes) : []),
    [active],
  );

  const displayGraph = useMemo(() => {
    if (!active) return null;
    if (!collapsedGroups.size) return active;
    const collapsed = collapseGroups(active.nodes, active.edges, collapsedGroups, groups);
    return { ...active, nodes: collapsed.nodes, edges: collapsed.edges };
  }, [active, collapsedGroups, groups]);

  const projection = useMemo(
    () => (displayGraph ? project(displayGraph, view) : null),
    [displayGraph, view],
  );

  const pathTrace = useMemo(() => {
    if (!displayGraph || !pathAnchorId || !focusId || pathAnchorId === focusId) {
      return null;
    }
    return shortestPath(displayGraph.edges, pathAnchorId, focusId);
  }, [displayGraph, pathAnchorId, focusId]);

  const pathNodeIds = pathTrace?.found ? pathTrace.nodeIds : [];

  const diff = useMemo(() => {
    if (!workflow || !previousWorkflow) return null;
    return diffGraphs(graphFromWorkflow(previousWorkflow), graphFromWorkflow(workflow));
  }, [workflow, previousWorkflow]);

  const onSelect = useCallback((id: string) => {
    setFocusId(id);
  }, []);

  const onLodMessage = useCallback((msg: string) => {
    setLodMessage(msg);
  }, []);

  const proposeDemoPatch = useCallback(() => {
    if (!active) return;
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
    const raw = {
      schema_version: 1,
      summary: "Suggested: add review question node (schema-valid, reviewable)",
      ops: [
        {
          op: "add_node",
          node: {
            id,
            type: "Question",
            label: "What remains uncertain?",
            properties: { ai_suggested: true },
          },
        },
      ],
    };
    const parsed = parseGraphPatch(raw);
    if (!parsed.ok) {
      setPendingPatch(null);
      setPatchError(parsed.error);
      return;
    }
    setPendingPatch(parsed.patch);
    setPatchError("");
  }, [active]);

  const applyPending = useCallback(() => {
    if (!active || !pendingPatch) return;
    const recheck = parseGraphPatch(pendingPatch);
    if (!recheck.ok) {
      setPatchError(recheck.error);
      return;
    }
    const result = applyGraphPatch(active, recheck.patch);
    if (!result.ok) {
      setPatchError(result.error);
      return;
    }
    setOverlayGraph(result.graph);
    setPendingPatch(null);
    setPatchError("");
  }, [active, pendingPatch]);

  const outline: OutlineItem[] = projection?.outline ?? [];

  const setPathFromFocus = useCallback(() => {
    if (!focusId) return;
    if (!pathAnchorId) {
      setPathAnchorId(focusId);
      return;
    }
    if (pathAnchorId === focusId) {
      setPathAnchorId(null);
      return;
    }
    // keep anchor; focus is endpoint — pathTrace recomputes
  }, [focusId, pathAnchorId]);

  const toggleGroupCollapse = useCallback((gid: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(gid)) next.delete(gid);
      else next.add(gid);
      return next;
    });
  }, []);

  const pathStatus =
    pathAnchorId && focusId && pathAnchorId !== focusId
      ? pathTrace?.found
        ? `Path ${pathAnchorId.slice(0, 8)}… → ${focusId.slice(0, 8)}… (${pathTrace.nodeIds.length} nodes)`
        : "No path between path anchor and focus"
      : pathAnchorId
        ? `Path anchor set (${pathAnchorId.slice(0, 8)}…). Select another node as endpoint.`
        : "";

  return (
    <div className="suite">
      <div className="suite-toolbar" role="toolbar" aria-label="Graph views">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            type="button"
            className={view === v.id ? "primary" : undefined}
            aria-pressed={view === v.id}
            onClick={() => {
              setView(v.id);
              setPage(0);
            }}
          >
            {v.label}
          </button>
        ))}
        <button type="button" className="ghost" onClick={proposeDemoPatch} disabled={!active}>
          Propose AI patch…
        </button>
        <button
          type="button"
          className="ghost"
          onClick={setPathFromFocus}
          disabled={!focusId}
          title="Set path anchor from focus, or clear when same"
        >
          {pathAnchorId ? "Path: set endpoint / clear" : "Path: set anchor"}
        </button>
        <button
          type="button"
          className="ghost"
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={page <= 0}
        >
          Prev page
        </button>
        <button
          type="button"
          className="ghost"
          onClick={() => setPage((p) => p + 1)}
        >
          Next page
        </button>
      </div>

      {groups.length > 0 ? (
        <div className="suite-toolbar" role="toolbar" aria-label="Subflow groups">
          {groups.map((g) => (
            <button
              key={g.id}
              type="button"
              className="ghost"
              aria-pressed={collapsedGroups.has(g.id)}
              onClick={() => toggleGroupCollapse(g.id)}
            >
              {collapsedGroups.has(g.id) ? "Expand" : "Collapse"} {g.label} (
              {g.memberIds.length})
            </button>
          ))}
        </div>
      ) : null}

      <div
        id={liveId}
        className="suite-live"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {[
          liveMessage,
          lodMessage,
          pathStatus,
          focusId
            ? `Focused ${outline.find((o) => o.id === focusId)?.label ?? focusId}`
            : view.replace("_", " "),
        ]
          .filter(Boolean)
          .join(" · ")}
      </div>

      <div className="suite-body">
        <div className="graph-wrap suite-canvas" aria-label={`${view} canvas`}>
          {view === "workflow_dag" ? (
            <WorkflowGraph
              workflow={workflow}
              focusId={focusId}
              onSelect={onSelect}
              nodeStatuses={undefined}
              pathNodeIds={pathNodeIds}
              page={page}
              onLodMessage={onLodMessage}
            />
          ) : null}
          {view === "mind_map" && projection ? (
            <MindMapView
              projection={projection}
              focusId={focusId}
              onSelect={onSelect}
              pathNodeIds={pathNodeIds}
              page={page}
              onLodMessage={onLodMessage}
            />
          ) : null}
          {view === "tree_outline" && projection ? (
            <TreeOutlineView projection={projection} focusId={focusId} onSelect={onSelect} />
          ) : null}
          {view === "knowledge" && projection ? (
            <KnowledgeGraphView
              projection={projection}
              focusId={focusId}
              onSelect={onSelect}
              pathNodeIds={pathNodeIds}
              page={page}
              onLodMessage={onLodMessage}
            />
          ) : null}
          {view === "lineage" && projection ? (
            <LineageView
              projection={projection}
              focusId={focusId}
              onSelect={onSelect}
              pathNodeIds={pathNodeIds}
            />
          ) : null}
          {!workflow ? (
            <p className="status" style={{ padding: "1rem" }}>
              Generate a workflow to populate graph projections.
            </p>
          ) : null}
        </div>

        <GraphOutline
          items={outline}
          focusId={focusId}
          onSelect={onSelect}
          labelledBy={liveId}
        />
      </div>

      {diff ? <GraphDiffPanel diff={diff} /> : null}

      {pendingPatch ? (
        <div className="patch-review" role="region" aria-label="AI graph patch review">
          <h3>Reviewable AI patch</h3>
          <p className="muted">Schema-valid only — apply re-validates before mutate.</p>
          <p>{pendingPatch.summary}</p>
          <pre>{JSON.stringify(pendingPatch, null, 2)}</pre>
          {patchError ? (
            <p className="error" role="alert">
              {patchError}
            </p>
          ) : null}
          <div className="actions">
            <button type="button" className="primary" onClick={applyPending}>
              Apply patch
            </button>
            <button
              type="button"
              onClick={() => {
                setPendingPatch(null);
                setPatchError("");
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      ) : null}
      {patchError && !pendingPatch ? (
        <p className="error" role="alert">
          {patchError}
        </p>
      ) : null}
    </div>
  );
}
