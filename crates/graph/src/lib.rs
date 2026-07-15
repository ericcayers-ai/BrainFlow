//! Canonical typed property graph + projections, diff, and patch validation.
//! Layout engines live in the UI; this crate owns portable semantics.

use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet, VecDeque};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum GraphError {
    #[error("dangling edge endpoint: {0}")]
    DanglingEndpoint(String),
    #[error("incompatible edge {edge_type} between {from_type} → {to_type}")]
    IncompatibleEdge {
        edge_type: String,
        from_type: String,
        to_type: String,
    },
    #[error("invalid patch: {0}")]
    InvalidPatch(String),
    #[error("unknown node type: {0}")]
    UnknownNodeType(String),
    #[error("unknown edge type: {0}")]
    UnknownEdgeType(String),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "PascalCase")]
pub enum NodeType {
    File,
    Note,
    Block,
    Entity,
    Goal,
    Constraint,
    Task,
    Decision,
    Question,
    Evidence,
    Artifact,
    WorkflowStep,
    Person,
}

impl NodeType {
    pub fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "File" | "file" => Self::File,
            "Note" | "note" => Self::Note,
            "Block" | "block" => Self::Block,
            "Entity" | "entity" => Self::Entity,
            "Goal" | "goal" => Self::Goal,
            "Constraint" | "constraint" => Self::Constraint,
            "Task" | "task" => Self::Task,
            "Decision" | "decision" => Self::Decision,
            "Question" | "question" => Self::Question,
            "Evidence" | "evidence" => Self::Evidence,
            "Artifact" | "artifact" => Self::Artifact,
            "WorkflowStep" | "workflow_step" => Self::WorkflowStep,
            "Person" | "person" => Self::Person,
            _ => return None,
        })
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::File => "File",
            Self::Note => "Note",
            Self::Block => "Block",
            Self::Entity => "Entity",
            Self::Goal => "Goal",
            Self::Constraint => "Constraint",
            Self::Task => "Task",
            Self::Decision => "Decision",
            Self::Question => "Question",
            Self::Evidence => "Evidence",
            Self::Artifact => "Artifact",
            Self::WorkflowStep => "WorkflowStep",
            Self::Person => "Person",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum EdgeType {
    LinksTo,
    DerivedFrom,
    Supports,
    Contradicts,
    DependsOn,
    Produces,
    AssignedTo,
    Precedes,
    Mentions,
}

impl EdgeType {
    pub fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "links_to" => Self::LinksTo,
            "derived_from" => Self::DerivedFrom,
            "supports" => Self::Supports,
            "contradicts" => Self::Contradicts,
            "depends_on" => Self::DependsOn,
            "produces" => Self::Produces,
            "assigned_to" => Self::AssignedTo,
            "precedes" => Self::Precedes,
            "mentions" => Self::Mentions,
            _ => return None,
        })
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::LinksTo => "links_to",
            Self::DerivedFrom => "derived_from",
            Self::Supports => "supports",
            Self::Contradicts => "contradicts",
            Self::DependsOn => "depends_on",
            Self::Produces => "produces",
            Self::AssignedTo => "assigned_to",
            Self::Precedes => "precedes",
            Self::Mentions => "mentions",
        }
    }
}

fn edge_compatible(edge: &EdgeType, from: &NodeType, to: &NodeType) -> bool {
    match edge {
        EdgeType::LinksTo => matches!(from, NodeType::Note | NodeType::Block | NodeType::File)
            && matches!(to, NodeType::Note | NodeType::Block | NodeType::File),
        EdgeType::DerivedFrom => {
            matches!(
                from,
                NodeType::Artifact | NodeType::Evidence | NodeType::WorkflowStep | NodeType::Note
            )
        }
        EdgeType::Supports | EdgeType::Contradicts => {
            matches!(from, NodeType::Evidence | NodeType::Note | NodeType::Entity)
                && matches!(
                    to,
                    NodeType::Decision | NodeType::Question | NodeType::Entity | NodeType::Goal
                )
        }
        EdgeType::DependsOn | EdgeType::Precedes => {
            matches!(
                (from, to),
                (NodeType::Task, NodeType::Task)
                    | (NodeType::WorkflowStep, NodeType::WorkflowStep)
                    | (NodeType::Goal, NodeType::Goal)
                    | (NodeType::Goal, NodeType::Task)
                    | (NodeType::Goal, NodeType::WorkflowStep)
                    | (NodeType::Task, NodeType::WorkflowStep)
                    | (NodeType::WorkflowStep, NodeType::Task)
            )
        }
        EdgeType::Produces => {
            matches!(from, NodeType::WorkflowStep | NodeType::Task)
                && matches!(to, NodeType::Artifact | NodeType::Note)
        }
        EdgeType::AssignedTo => {
            matches!(from, NodeType::Task) && matches!(to, NodeType::Person)
        }
        EdgeType::Mentions => true,
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphNode {
    pub id: Uuid,
    #[serde(rename = "type")]
    pub node_type: NodeType,
    pub label: String,
    #[serde(default)]
    pub properties: Map<String, Value>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub locators: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provenance: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphEdge {
    pub id: Uuid,
    #[serde(rename = "type")]
    pub edge_type: EdgeType,
    pub from: Uuid,
    pub to: Uuid,
    #[serde(default)]
    pub properties: Map<String, Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub weight: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provenance: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ViewKind {
    WorkflowDag,
    MindMap,
    TreeOutline,
    Knowledge,
    Lineage,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SavedView {
    pub id: String,
    pub kind: ViewKind,
    #[serde(default)]
    pub layout: String,
    #[serde(default)]
    pub filters: Map<String, Value>,
    #[serde(default)]
    pub pinned_positions: Map<String, Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CanonicalGraph {
    pub schema_version: u32,
    pub graph_id: Uuid,
    pub nodes: Vec<GraphNode>,
    pub edges: Vec<GraphEdge>,
    #[serde(default)]
    pub views: Vec<SavedView>,
}

impl CanonicalGraph {
    pub fn new() -> Self {
        Self {
            schema_version: 1,
            graph_id: Uuid::new_v4(),
            nodes: vec![],
            edges: vec![],
            views: vec![],
        }
    }

    pub fn validate(&self) -> Result<(), GraphError> {
        let types: HashMap<Uuid, NodeType> = self
            .nodes
            .iter()
            .map(|n| (n.id, n.node_type.clone()))
            .collect();
        for e in &self.edges {
            let from_t = types
                .get(&e.from)
                .ok_or_else(|| GraphError::DanglingEndpoint(e.from.to_string()))?;
            let to_t = types
                .get(&e.to)
                .ok_or_else(|| GraphError::DanglingEndpoint(e.to.to_string()))?;
            if !edge_compatible(&e.edge_type, from_t, to_t) {
                return Err(GraphError::IncompatibleEdge {
                    edge_type: e.edge_type.as_str().into(),
                    from_type: from_t.as_str().into(),
                    to_type: to_t.as_str().into(),
                });
            }
        }
        Ok(())
    }

    pub fn node_index(&self) -> HashMap<Uuid, &GraphNode> {
        self.nodes.iter().map(|n| (n.id, n)).collect()
    }
}

impl Default for CanonicalGraph {
    fn default() -> Self {
        Self::new()
    }
}

/// Projection consumed by UI engines (React Flow / Cytoscape / outline).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphProjection {
    pub schema_version: u32,
    pub view: ViewKind,
    pub nodes: Vec<Value>,
    pub edges: Vec<Value>,
    pub outline: Vec<OutlineItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutlineItem {
    pub id: String,
    pub label: String,
    pub node_type: String,
    pub depth: u32,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub children: Vec<String>,
}

pub fn project(graph: &CanonicalGraph, view: ViewKind) -> Result<GraphProjection, GraphError> {
    graph.validate()?;
    match view {
        ViewKind::WorkflowDag => project_workflow(graph),
        ViewKind::MindMap => project_mind_map(graph),
        ViewKind::TreeOutline => project_tree(graph),
        ViewKind::Knowledge => project_knowledge(graph),
        ViewKind::Lineage => project_lineage(graph),
    }
}

fn filter_nodes<'a>(
    graph: &'a CanonicalGraph,
    pred: impl Fn(&GraphNode) -> bool,
) -> Vec<&'a GraphNode> {
    graph.nodes.iter().filter(|n| pred(n)).collect()
}

fn project_workflow(graph: &CanonicalGraph) -> Result<GraphProjection, GraphError> {
    let steps = filter_nodes(graph, |n| matches!(n.node_type, NodeType::WorkflowStep | NodeType::Task | NodeType::Goal));
    let ids: HashSet<Uuid> = steps.iter().map(|n| n.id).collect();
    let edges: Vec<_> = graph
        .edges
        .iter()
        .filter(|e| {
            ids.contains(&e.from)
                && ids.contains(&e.to)
                && matches!(e.edge_type, EdgeType::Precedes | EdgeType::DependsOn)
        })
        .collect();
    Ok(build_projection(ViewKind::WorkflowDag, &steps, &edges))
}

fn project_mind_map(graph: &CanonicalGraph) -> Result<GraphProjection, GraphError> {
    let nodes = filter_nodes(graph, |n| {
        matches!(
            n.node_type,
            NodeType::Goal | NodeType::Question | NodeType::Entity | NodeType::Task | NodeType::Note
        )
    });
    let ids: HashSet<Uuid> = nodes.iter().map(|n| n.id).collect();
    let edges: Vec<_> = graph
        .edges
        .iter()
        .filter(|e| ids.contains(&e.from) && ids.contains(&e.to))
        .collect();
    Ok(build_projection(ViewKind::MindMap, &nodes, &edges))
}

fn project_tree(graph: &CanonicalGraph) -> Result<GraphProjection, GraphError> {
    project_mind_map(graph).map(|mut p| {
        p.view = ViewKind::TreeOutline;
        p
    })
}

fn project_knowledge(graph: &CanonicalGraph) -> Result<GraphProjection, GraphError> {
    let nodes: Vec<_> = graph.nodes.iter().collect();
    let edges: Vec<_> = graph.edges.iter().collect();
    Ok(build_projection(ViewKind::Knowledge, &nodes, &edges))
}

fn project_lineage(graph: &CanonicalGraph) -> Result<GraphProjection, GraphError> {
    let nodes = filter_nodes(graph, |n| {
        matches!(
            n.node_type,
            NodeType::File
                | NodeType::Evidence
                | NodeType::WorkflowStep
                | NodeType::Artifact
                | NodeType::Note
        )
    });
    let ids: HashSet<Uuid> = nodes.iter().map(|n| n.id).collect();
    let edges: Vec<_> = graph
        .edges
        .iter()
        .filter(|e| {
            ids.contains(&e.from)
                && ids.contains(&e.to)
                && matches!(
                    e.edge_type,
                    EdgeType::DerivedFrom | EdgeType::Produces | EdgeType::Supports
                )
        })
        .collect();
    Ok(build_projection(ViewKind::Lineage, &nodes, &edges))
}

fn build_projection(
    view: ViewKind,
    nodes: &[&GraphNode],
    edges: &[&GraphEdge],
) -> GraphProjection {
    let outline = outline_from(nodes, edges);
    GraphProjection {
        schema_version: 1,
        view,
        nodes: nodes
            .iter()
            .map(|n| {
                json!({
                    "id": n.id,
                    "type": n.node_type.as_str(),
                    "label": n.label,
                    "properties": n.properties,
                })
            })
            .collect(),
        edges: edges
            .iter()
            .map(|e| {
                json!({
                    "id": e.id,
                    "type": e.edge_type.as_str(),
                    "from": e.from,
                    "to": e.to,
                    "properties": e.properties,
                })
            })
            .collect(),
        outline,
    }
}

fn outline_from(nodes: &[&GraphNode], edges: &[&GraphEdge]) -> Vec<OutlineItem> {
    let mut children: HashMap<Uuid, Vec<Uuid>> = HashMap::new();
    let mut indeg: HashMap<Uuid, usize> = nodes.iter().map(|n| (n.id, 0)).collect();
    for e in edges {
        children.entry(e.from).or_default().push(e.to);
        *indeg.entry(e.to).or_default() += 1;
    }
    let labels: HashMap<Uuid, (&str, &str)> = nodes
        .iter()
        .map(|n| (n.id, (n.label.as_str(), n.node_type.as_str())))
        .collect();
    let mut roots: Vec<Uuid> = indeg
        .iter()
        .filter(|(_, d)| **d == 0)
        .map(|(k, _)| *k)
        .collect();
    roots.sort();
    let mut out = Vec::new();
    let mut q: VecDeque<(Uuid, u32)> = roots.into_iter().map(|id| (id, 0)).collect();
    let mut seen = HashSet::new();
    while let Some((id, depth)) = q.pop_front() {
        if !seen.insert(id) {
            continue;
        }
        let (label, nt) = labels.get(&id).copied().unwrap_or(("", "Unknown"));
        let kids = children.get(&id).cloned().unwrap_or_default();
        out.push(OutlineItem {
            id: id.to_string(),
            label: label.to_string(),
            node_type: nt.to_string(),
            depth,
            children: kids.iter().map(|k| k.to_string()).collect(),
        });
        for k in kids {
            q.push_back((k, depth + 1));
        }
    }
    // orphans
    for n in nodes {
        if !seen.contains(&n.id) {
            out.push(OutlineItem {
                id: n.id.to_string(),
                label: n.label.clone(),
                node_type: n.node_type.as_str().into(),
                depth: 0,
                children: vec![],
            });
        }
    }
    out
}

/// Build canonical graph from workflow IR JSON.
pub fn graph_from_workflow(workflow: &Value) -> Result<CanonicalGraph, GraphError> {
    let mut graph = CanonicalGraph::new();
    let goal_id = Uuid::new_v4();
    let goal_label = workflow
        .pointer("/goal/statement")
        .and_then(|v| v.as_str())
        .unwrap_or("Goal")
        .to_string();
    graph.nodes.push(GraphNode {
        id: goal_id,
        node_type: NodeType::Goal,
        label: goal_label,
        properties: Map::new(),
        locators: vec![],
        provenance: None,
    });

    let mut id_map: HashMap<String, Uuid> = HashMap::new();
    if let Some(nodes) = workflow.get("nodes").and_then(|v| v.as_array()) {
        for n in nodes {
            let raw = n.get("id").and_then(|v| v.as_str()).unwrap_or("");
            let uuid = Uuid::parse_str(raw).unwrap_or_else(|_| Uuid::new_v4());
            id_map.insert(raw.to_string(), uuid);
            let mut props = Map::new();
            if let Some(t) = n.get("type") {
                props.insert("ir_type".into(), t.clone());
            }
            if let Some(p) = n.get("permission_class") {
                props.insert("permission_class".into(), p.clone());
            }
            graph.nodes.push(GraphNode {
                id: uuid,
                node_type: NodeType::WorkflowStep,
                label: n
                    .get("title")
                    .and_then(|v| v.as_str())
                    .unwrap_or("step")
                    .to_string(),
                properties: props,
                locators: vec![],
                provenance: None,
            });
        }
    }

    // Goal precedes first roots
    if let Some(first) = graph.nodes.iter().find(|n| n.node_type == NodeType::WorkflowStep) {
        graph.edges.push(GraphEdge {
            id: Uuid::new_v4(),
            edge_type: EdgeType::Precedes,
            from: goal_id,
            to: first.id,
            properties: Map::new(),
            weight: None,
            provenance: None,
        });
    }

    if let Some(edges) = workflow.get("edges").and_then(|v| v.as_array()) {
        for e in edges {
            let frm = e
                .get("from")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .split(':')
                .next()
                .unwrap_or("");
            let to = e
                .get("to")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .split(':')
                .next()
                .unwrap_or("");
            if let (Some(f), Some(t)) = (id_map.get(frm), id_map.get(to)) {
                graph.edges.push(GraphEdge {
                    id: Uuid::parse_str(e.get("id").and_then(|v| v.as_str()).unwrap_or(""))
                        .unwrap_or_else(|_| Uuid::new_v4()),
                    edge_type: EdgeType::Precedes,
                    from: *f,
                    to: *t,
                    properties: Map::new(),
                    weight: None,
                    provenance: None,
                });
            }
        }
    }

    graph.views.push(SavedView {
        id: "default-dag".into(),
        kind: ViewKind::WorkflowDag,
        layout: "layered".into(),
        filters: Map::new(),
        pinned_positions: Map::new(),
    });
    graph.validate()?;
    Ok(graph)
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GraphDiff {
    pub nodes_added: Vec<Uuid>,
    pub nodes_removed: Vec<Uuid>,
    pub nodes_changed: Vec<Uuid>,
    pub edges_added: Vec<Uuid>,
    pub edges_removed: Vec<Uuid>,
    pub edges_changed: Vec<Uuid>,
}

pub fn diff_graphs(a: &CanonicalGraph, b: &CanonicalGraph) -> GraphDiff {
    let a_nodes: BTreeMap<_, _> = a.nodes.iter().map(|n| (n.id, n)).collect();
    let b_nodes: BTreeMap<_, _> = b.nodes.iter().map(|n| (n.id, n)).collect();
    let a_ids: BTreeSet<_> = a_nodes.keys().copied().collect();
    let b_ids: BTreeSet<_> = b_nodes.keys().copied().collect();

    let mut d = GraphDiff::default();
    d.nodes_added = b_ids.difference(&a_ids).copied().collect();
    d.nodes_removed = a_ids.difference(&b_ids).copied().collect();
    for id in a_ids.intersection(&b_ids) {
        let na = a_nodes[id];
        let nb = b_nodes[id];
        if na.label != nb.label || na.node_type != nb.node_type || na.properties != nb.properties {
            d.nodes_changed.push(*id);
        }
    }

    let a_edges: BTreeMap<_, _> = a.edges.iter().map(|e| (e.id, e)).collect();
    let b_edges: BTreeMap<_, _> = b.edges.iter().map(|e| (e.id, e)).collect();
    let ae: BTreeSet<_> = a_edges.keys().copied().collect();
    let be: BTreeSet<_> = b_edges.keys().copied().collect();
    d.edges_added = be.difference(&ae).copied().collect();
    d.edges_removed = ae.difference(&be).copied().collect();
    for id in ae.intersection(&be) {
        let ea = a_edges[id];
        let eb = b_edges[id];
        if ea.from != eb.from
            || ea.to != eb.to
            || ea.edge_type != eb.edge_type
            || ea.properties != eb.properties
        {
            d.edges_changed.push(*id);
        }
    }
    d
}

/// AI graph patches must be schema-shaped op lists; validated before apply.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum GraphPatchOp {
    AddNode {
        node: GraphNode,
    },
    RemoveNode {
        id: Uuid,
    },
    UpdateNode {
        id: Uuid,
        label: Option<String>,
        properties: Option<Map<String, Value>>,
    },
    AddEdge {
        edge: GraphEdge,
    },
    RemoveEdge {
        id: Uuid,
    },
}

pub fn validate_and_apply_patch(
    graph: &CanonicalGraph,
    ops: &[GraphPatchOp],
) -> Result<CanonicalGraph, GraphError> {
    let mut next = graph.clone();
    for op in ops {
        match op {
            GraphPatchOp::AddNode { node } => {
                if next.nodes.iter().any(|n| n.id == node.id) {
                    return Err(GraphError::InvalidPatch(format!(
                        "duplicate node {}",
                        node.id
                    )));
                }
                next.nodes.push(node.clone());
            }
            GraphPatchOp::RemoveNode { id } => {
                next.nodes.retain(|n| n.id != *id);
                next.edges.retain(|e| e.from != *id && e.to != *id);
            }
            GraphPatchOp::UpdateNode {
                id,
                label,
                properties,
            } => {
                let node = next
                    .nodes
                    .iter_mut()
                    .find(|n| n.id == *id)
                    .ok_or_else(|| GraphError::InvalidPatch(format!("missing node {id}")))?;
                if let Some(l) = label {
                    node.label = l.clone();
                }
                if let Some(p) = properties {
                    node.properties = p.clone();
                }
            }
            GraphPatchOp::AddEdge { edge } => {
                next.edges.push(edge.clone());
            }
            GraphPatchOp::RemoveEdge { id } => {
                next.edges.retain(|e| e.id != *id);
            }
        }
    }
    next.validate()?;
    Ok(next)
}

/// Legacy alias used by knowledge-workspace vault graph commands.
pub type NodeKind = NodeType;
pub type EdgeKind = EdgeType;

/// Build a knowledge projection from vault note paths and wikilink pairs.
/// `local_only` + `focus_path` limits to the focused note neighborhood.
pub fn knowledge_projection_from_links(
    note_paths: &[String],
    links: &[(String, String)],
    focus_path: Option<&str>,
    local_only: bool,
) -> GraphProjection {
    let mut path_to_id: HashMap<String, Uuid> = HashMap::new();
    let mut nodes: Vec<GraphNode> = Vec::new();
    for path in note_paths {
        let id = Uuid::new_v4();
        path_to_id.insert(path.clone(), id);
        let label = path.rsplit('/').next().unwrap_or(path).to_string();
        nodes.push(GraphNode {
            id,
            node_type: NodeType::Note,
            label,
            properties: {
                let mut m = Map::new();
                m.insert("path".into(), Value::String(path.clone()));
                m
            },
            locators: vec![path.clone()],
            provenance: None,
        });
    }

    let mut edges: Vec<GraphEdge> = Vec::new();
    for (from, to) in links {
        let (Some(&fid), Some(&tid)) = (path_to_id.get(from), path_to_id.get(to)) else {
            continue;
        };
        edges.push(GraphEdge {
            id: Uuid::new_v4(),
            edge_type: EdgeType::LinksTo,
            from: fid,
            to: tid,
            properties: Map::new(),
            weight: None,
            provenance: None,
        });
    }

    if local_only {
        if let Some(focus) = focus_path {
            if let Some(&fid) = path_to_id.get(focus) {
                let mut keep = HashSet::new();
                keep.insert(fid);
                for e in &edges {
                    if e.from == fid || e.to == fid {
                        keep.insert(e.from);
                        keep.insert(e.to);
                    }
                }
                nodes.retain(|n| keep.contains(&n.id));
                edges.retain(|e| keep.contains(&e.from) && keep.contains(&e.to));
            } else {
                nodes.clear();
                edges.clear();
            }
        }
    }

    let refs_n: Vec<&GraphNode> = nodes.iter().collect();
    let refs_e: Vec<&GraphEdge> = edges.iter().collect();
    let mut projection = build_projection(ViewKind::Knowledge, &refs_n, &refs_e);
    // Include scope hint for UI
    for n in &mut projection.nodes {
        if let Some(obj) = n.as_object_mut() {
            obj.entry("scope").or_insert_with(|| {
                Value::String(if local_only { "local" } else { "global" }.into())
            });
        }
    }
    projection
}

/// Minimal workflow-IR → graph projection for the foundation slice (compat).
pub fn projection_from_workflow_nodes(
    nodes: &[(Uuid, String)],
    edges: &[(Uuid, Uuid)],
) -> GraphProjection {
    let graph_nodes: Vec<GraphNode> = nodes
        .iter()
        .map(|(id, label)| GraphNode {
            id: *id,
            node_type: NodeType::WorkflowStep,
            label: label.clone(),
            properties: Map::new(),
            locators: vec![],
            provenance: None,
        })
        .collect();
    let graph_edges: Vec<GraphEdge> = edges
        .iter()
        .map(|(from, to)| GraphEdge {
            id: Uuid::new_v4(),
            from: *from,
            to: *to,
            edge_type: EdgeType::Precedes,
            properties: Map::new(),
            weight: None,
            provenance: None,
        })
        .collect();
    let refs_n: Vec<&GraphNode> = graph_nodes.iter().collect();
    let refs_e: Vec<&GraphEdge> = graph_edges.iter().collect();
    build_projection(ViewKind::WorkflowDag, &refs_n, &refs_e)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn workflow_roundtrip_projection() {
        let wf = json!({
            "goal": {"statement": "Study"},
            "nodes": [
                {"id": "11111111-1111-1111-1111-111111111111", "type": "summarize", "title": "Sum", "permission_class": "safe_overlay"},
                {"id": "22222222-2222-2222-2222-222222222222", "type": "write_artifact", "title": "Write", "permission_class": "safe_overlay"}
            ],
            "edges": [{
                "id": "33333333-3333-3333-3333-333333333333",
                "from": "11111111-1111-1111-1111-111111111111:out",
                "to": "22222222-2222-2222-2222-222222222222:in",
                "kind": "data"
            }]
        });
        let g = graph_from_workflow(&wf).unwrap();
        let p = project(&g, ViewKind::WorkflowDag).unwrap();
        assert!(!p.outline.is_empty());
        let p2 = project(&g, ViewKind::Lineage).unwrap();
        assert_eq!(p2.view, ViewKind::Lineage);
    }

    #[test]
    fn patch_rejected_when_dangling() {
        let g = CanonicalGraph::new();
        let op = GraphPatchOp::AddEdge {
            edge: GraphEdge {
                id: Uuid::new_v4(),
                edge_type: EdgeType::Precedes,
                from: Uuid::new_v4(),
                to: Uuid::new_v4(),
                properties: Map::new(),
                weight: None,
                provenance: None,
            },
        };
        assert!(validate_and_apply_patch(&g, &[op]).is_err());
    }

    #[test]
    fn diff_detects_added_node() {
        let a = CanonicalGraph::new();
        let mut b = a.clone();
        let id = Uuid::new_v4();
        b.nodes.push(GraphNode {
            id,
            node_type: NodeType::Note,
            label: "n".into(),
            properties: Map::new(),
            locators: vec![],
            provenance: None,
        });
        let d = diff_graphs(&a, &b);
        assert_eq!(d.nodes_added, vec![id]);
    }

    #[test]
    fn knowledge_projection_local_neighborhood() {
        let notes = vec![
            "notes/a.md".into(),
            "notes/b.md".into(),
            "notes/c.md".into(),
        ];
        let links = vec![
            ("notes/a.md".into(), "notes/b.md".into()),
            ("notes/c.md".into(), "notes/a.md".into()),
        ];
        let g = knowledge_projection_from_links(&notes, &links, Some("notes/a.md"), true);
        assert_eq!(g.view, ViewKind::Knowledge);
        assert_eq!(g.nodes.len(), 3);
        assert_eq!(g.edges.len(), 2);
    }
}

