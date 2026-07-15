import type { GraphDiff } from "../graph/model";

export default function GraphDiffPanel({ diff }: { diff: GraphDiff }) {
  const total =
    diff.nodes_added.length +
    diff.nodes_removed.length +
    diff.nodes_changed.length +
    diff.edges_added.length +
    diff.edges_removed.length +
    diff.edges_changed.length;
  return (
    <div className="graph-diff" role="region" aria-label="Workflow graph diff">
      <h3>Version diff</h3>
      {total === 0 ? (
        <p className="status">No structural changes vs previous workflow.</p>
      ) : (
        <ul>
          <li>Nodes +{diff.nodes_added.length} / −{diff.nodes_removed.length} / ~{diff.nodes_changed.length}</li>
          <li>Edges +{diff.edges_added.length} / −{diff.edges_removed.length} / ~{diff.edges_changed.length}</li>
        </ul>
      )}
    </div>
  );
}
