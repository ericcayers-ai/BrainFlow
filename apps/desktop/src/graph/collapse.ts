import type { GraphEdge, GraphNode } from "./model";

export type CollapseGroup = {
  id: string;
  label: string;
  memberIds: string[];
};

/**
 * Collapse marked groups/subflows into single synthetic nodes.
 * Group membership: `node.properties.group_id` (string) or explicit `groups`.
 */
export function collapseGroups(
  nodes: GraphNode[],
  edges: GraphEdge[],
  collapsedGroupIds: Set<string>,
  groups?: CollapseGroup[],
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (!collapsedGroupIds.size) return { nodes, edges };

  const inferred = new Map<string, string[]>();
  for (const n of nodes) {
    const gid = n.properties?.group_id;
    if (typeof gid === "string" && collapsedGroupIds.has(gid)) {
      const list = inferred.get(gid) ?? [];
      list.push(n.id);
      inferred.set(gid, list);
    }
  }
  for (const g of groups ?? []) {
    if (collapsedGroupIds.has(g.id)) {
      inferred.set(g.id, [...g.memberIds]);
    }
  }

  if (!inferred.size) return { nodes, edges };

  const memberToGroup = new Map<string, string>();
  const groupNodes: GraphNode[] = [];
  for (const [gid, members] of inferred) {
    const label =
      groups?.find((g) => g.id === gid)?.label ?? `Subflow ${gid.slice(0, 8)}`;
    for (const m of members) memberToGroup.set(m, gid);
    groupNodes.push({
      id: `group:${gid}`,
      type: "WorkflowStep",
      label: `${label} (${members.length})`,
      properties: {
        synthetic: true,
        collapsed_group: true,
        group_id: gid,
        member_ids: members,
      },
    });
  }

  const kept = nodes.filter((n) => !memberToGroup.has(n.id));
  const outNodes = [...kept, ...groupNodes];
  const resolve = (id: string) => {
    const g = memberToGroup.get(id);
    return g ? `group:${g}` : id;
  };
  const seen = new Set<string>();
  const outEdges: GraphEdge[] = [];
  for (const e of edges) {
    const from = resolve(e.from);
    const to = resolve(e.to);
    if (from === to) continue;
    const key = `${from}|${to}|${e.type}`;
    if (seen.has(key)) continue;
    seen.add(key);
    outEdges.push({
      ...e,
      id: seen.size === 1 ? e.id : `${e.id}-c`,
      from,
      to,
    });
  }
  return { nodes: outNodes, edges: outEdges };
}

/** Discover group ids present on nodes. */
export function discoverGroups(nodes: GraphNode[]): CollapseGroup[] {
  const map = new Map<string, string[]>();
  for (const n of nodes) {
    const gid = n.properties?.group_id;
    if (typeof gid !== "string") continue;
    const list = map.get(gid) ?? [];
    list.push(n.id);
    map.set(gid, list);
  }
  return [...map.entries()].map(([id, memberIds]) => ({
    id,
    label: `Group ${id}`,
    memberIds,
  }));
}
