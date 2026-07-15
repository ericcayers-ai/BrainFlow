//! Deterministic authorization, budget, and workflow policy gates.

//! AI cannot bypass these checks.



use serde_json::Value;

use std::collections::{HashMap, HashSet, VecDeque};

use thiserror::Error;



#[derive(Debug, Error, PartialEq, Eq)]

pub enum PolicyError {

    #[error("schema_version missing or unsupported")]

    UnsupportedSchema,

    #[error("permission class requires approval: {0}")]

    ApprovalRequired(String),

    #[error("policy rejection: {0}")]

    Rejected(String),

}



/// Canonical permission classes (docs/AI_SAFETY_AND_AGENCY.md).

#[derive(Debug, Clone, Copy, PartialEq, Eq)]

pub enum PermissionClass {

    Read,

    SafeOverlay,

    VaultMutate,

    SourceMutate,

    NetworkEgress,

    Publish,

    Shell,

    Credentials,

}



impl PermissionClass {

    pub fn parse(s: &str) -> Option<Self> {

        Some(match s {

            "read" => Self::Read,

            "safe_overlay" => Self::SafeOverlay,

            "vault_mutate" | "approval_required" => Self::VaultMutate,

            "source_mutate" => Self::SourceMutate,

            "network_egress" | "network" => Self::NetworkEgress,

            "publish" => Self::Publish,

            "shell" => Self::Shell,

            "credentials" => Self::Credentials,

            _ => return None,

        })

    }



    pub fn as_str(self) -> &'static str {

        match self {

            Self::Read => "read",

            Self::SafeOverlay => "safe_overlay",

            Self::VaultMutate => "vault_mutate",

            Self::SourceMutate => "source_mutate",

            Self::NetworkEgress => "network_egress",

            Self::Publish => "publish",

            Self::Shell => "shell",

            Self::Credentials => "credentials",

        }

    }



    pub fn may_auto_apply(self) -> bool {

        matches!(self, Self::Read | Self::SafeOverlay)

    }

}



/// Fail closed if schema_version is absent or not 1.

pub fn require_workflow_schema_v1(doc: &Value) -> Result<(), PolicyError> {

    match doc.get("schema_version").and_then(|v| v.as_u64()) {

        Some(1) => Ok(()),

        _ => Err(PolicyError::UnsupportedSchema),

    }

}



pub fn assert_auto_apply_allowed(permission_class: &str) -> Result<(), PolicyError> {

    let class = PermissionClass::parse(permission_class)

        .ok_or_else(|| PolicyError::Rejected(format!("unknown class {permission_class}")))?;

    if class.may_auto_apply() {

        Ok(())

    } else {

        Err(PolicyError::ApprovalRequired(class.as_str().into()))

    }

}



/// Safe overlay writes must remain under `.brainflow/` managed paths.

pub fn assert_safe_overlay_path(path: &str) -> Result<(), PolicyError> {

    let p = path.replace('\\', "/");

    let p = p.trim_start_matches('/');

    if p.split('/').any(|seg| seg == "..") {

        return Err(PolicyError::Rejected("path traversal rejected".into()));

    }

    let ok = p.starts_with(".brainflow/artifacts/")

        || p.starts_with(".brainflow/workflows/")

        || p.starts_with(".brainflow/graphs/")

        || p.starts_with(".brainflow/templates/")

        || p.starts_with(".brainflow/runs/")

        || p.starts_with("artifacts/");

    if ok {

        Ok(())

    } else {

        Err(PolicyError::Rejected(format!(

            "path not under .brainflow overlay: {path}"

        )))

    }

}



#[derive(Debug, Clone, Default)]

pub struct PolicyReport {

    pub ok: bool,

    pub errors: Vec<String>,

    pub approvals_needed: Vec<(String, String)>,

}



/// Full deterministic workflow policy pass (cycles, budgets, tools, paths, classes).

pub fn validate_workflow_policy(doc: &Value) -> PolicyReport {

    let mut report = PolicyReport {

        ok: true,

        ..Default::default()

    };



    if let Err(e) = require_workflow_schema_v1(doc) {

        report.ok = false;

        report.errors.push(e.to_string());

        return report;

    }



    let nodes = match doc.get("nodes").and_then(|v| v.as_array()) {

        Some(n) if !n.is_empty() => n,

        _ => {

            report.ok = false;

            report.errors.push("nodes required".into());

            return report;

        }

    };



    let mut node_ids: HashSet<String> = HashSet::new();

    let mut loop_nodes: HashSet<String> = HashSet::new();



    for n in nodes {

        let id = n

            .get("id")

            .and_then(|v| v.as_str())

            .unwrap_or("")

            .to_string();

        if id.is_empty() {

            report.ok = false;

            report.errors.push("node missing id".into());

            continue;

        }

        node_ids.insert(id.clone());



        let class_raw = n

            .get("permission_class")

            .and_then(|v| v.as_str())

            .unwrap_or("");

        match PermissionClass::parse(class_raw) {

            None => {

                report.ok = false;

                report

                    .errors

                    .push(format!("node {id}: unknown permission_class {class_raw}"));

            }

            Some(c) if !c.may_auto_apply() => {

                report

                    .approvals_needed

                    .push((id.clone(), c.as_str().to_string()));

            }

            Some(_) => {}

        }



        if let Some(loop_obj) = n.get("review_loop") {

            let mi = loop_obj.get("max_iterations").and_then(|v| v.as_u64());

            match mi {

                Some(v) if (1..=10).contains(&v) => {

                    loop_nodes.insert(id.clone());

                }

                _ => {

                    report.ok = false;

                    report.errors.push(format!(

                        "node {id}: review_loop.max_iterations must be 1..10"

                    ));

                }

            }

        }



        if let Some(tools) = n.get("allowed_tools").and_then(|v| v.as_array()) {

            for t in tools {

                if let Some(name) = t.as_str() {

                    if matches!(name, "shell" | "git" | "publish" | "delete_source") {

                        match PermissionClass::parse(class_raw) {

                            Some(c) if c.may_auto_apply() => {

                                report.ok = false;

                                report.errors.push(format!(

                                    "node {id}: tool {name} incompatible with auto-apply class"

                                ));

                            }

                            _ => {}

                        }

                    }

                }

            }

        }

    }



    // Budgets vs hard caps

    if let Some(budgets) = doc.get("budgets") {

        if budgets

            .get("max_steps")

            .and_then(|v| v.as_u64())

            .unwrap_or(0)

            > 500

        {

            report.ok = false;

            report

                .errors

                .push("budgets.max_steps exceeds hard cap 500".into());

        }

        if budgets

            .get("max_parallel_jobs")

            .and_then(|v| v.as_u64())

            .unwrap_or(0)

            > 32

        {

            report.ok = false;

            report

                .errors

                .push("budgets.max_parallel_jobs exceeds hard cap 32".into());

        }

    }



    // Cycle detection (unbounded cycles rejected unless every node has review_loop)

    let mut adj: HashMap<String, Vec<String>> =

        node_ids.iter().map(|id| (id.clone(), vec![])).collect();

    if let Some(edges) = doc.get("edges").and_then(|v| v.as_array()) {

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

            if node_ids.contains(frm) && node_ids.contains(to) {

                adj.entry(frm.to_string()).or_default().push(to.to_string());

            }

        }

    }



    let mut visiting = HashSet::new();

    let mut visited = HashSet::new();

    let mut stack: Vec<String> = Vec::new();



    fn dfs(

        u: &str,

        adj: &HashMap<String, Vec<String>>,

        visiting: &mut HashSet<String>,

        visited: &mut HashSet<String>,

        stack: &mut Vec<String>,

        loop_nodes: &HashSet<String>,

        report: &mut PolicyReport,

    ) {

        if visiting.contains(u) {

            if let Some(idx) = stack.iter().position(|x| x == u) {

                let cycle: Vec<String> = stack[idx..].to_vec();

                if !cycle.iter().all(|c| loop_nodes.contains(c)) {

                    report.ok = false;

                    report

                        .errors

                        .push(format!("unbounded cycle involving {cycle:?}"));

                }

            }

            return;

        }

        if visited.contains(u) {

            return;

        }

        visiting.insert(u.to_string());

        stack.push(u.to_string());

        if let Some(vs) = adj.get(u) {

            for v in vs {

                dfs(v, adj, visiting, visited, stack, loop_nodes, report);

            }

        }

        stack.pop();

        visiting.remove(u);

        visited.insert(u.to_string());

    }



    for id in &node_ids {

        dfs(

            id,

            &adj,

            &mut visiting,

            &mut visited,

            &mut stack,

            &loop_nodes,

            &mut report,

        );

    }



    // Reachability smoke: at least one root (indegree 0)

    let mut indeg: HashMap<String, usize> = node_ids.iter().map(|i| (i.clone(), 0)).collect();

    for vs in adj.values() {

        for v in vs {

            *indeg.entry(v.clone()).or_default() += 1;

        }

    }

    let roots: Vec<_> = indeg.iter().filter(|(_, d)| **d == 0).map(|(k, _)| k.clone()).collect();

    if roots.is_empty() && !node_ids.is_empty() {

        // Fully cyclic — already flagged unless all review_loop

        if loop_nodes.len() != node_ids.len() {

            report.ok = false;

            report

                .errors

                .push("workflow has no root node (fully cyclic)".into());

        }

    } else {

        // BFS reachability from roots

        let mut seen = HashSet::new();

        let mut q: VecDeque<String> = roots.into_iter().collect();

        while let Some(u) = q.pop_front() {

            if !seen.insert(u.clone()) {

                continue;

            }

            if let Some(vs) = adj.get(&u) {

                for v in vs {

                    q.push_back(v.clone());

                }

            }

        }

        for id in &node_ids {

            if !seen.contains(id) {

                report

                    .errors

                    .push(format!("unreachable node {id}"));

                report.ok = false;

            }

        }

    }



    report

}



/// Authorize a concrete executor action.

pub fn authorize_action(

    permission_class: &str,

    write_path: Option<&str>,

) -> Result<(), PolicyError> {

    assert_auto_apply_allowed(permission_class)?;

    if let Some(path) = write_path {

        assert_safe_overlay_path(path)?;

    }

    Ok(())

}



#[cfg(test)]

mod tests {

    use super::*;

    use serde_json::json;



    #[test]

    fn safe_overlay_auto_applies() {

        assert!(assert_auto_apply_allowed("safe_overlay").is_ok());

        assert!(matches!(

            assert_auto_apply_allowed("shell"),

            Err(PolicyError::ApprovalRequired(_))

        ));

    }



    #[test]

    fn rejects_source_path_writes() {

        assert!(assert_safe_overlay_path("notes/welcome.md").is_err());

        assert!(assert_safe_overlay_path(".brainflow/artifacts/w/r/a.md").is_ok());

    }



    #[test]

    fn detects_unbounded_cycle() {

        let a = "11111111-1111-1111-1111-111111111111";

        let b = "22222222-2222-2222-2222-222222222222";

        let doc = json!({

            "schema_version": 1,

            "nodes": [

                {"id": a, "type": "summarize", "title": "A", "permission_class": "safe_overlay"},

                {"id": b, "type": "summarize", "title": "B", "permission_class": "safe_overlay"}

            ],

            "edges": [

                {"id": "e1", "from": format!("{a}:out"), "to": format!("{b}:in"), "kind": "data"},

                {"id": "e2", "from": format!("{b}:out"), "to": format!("{a}:in"), "kind": "data"}

            ],

            "budgets": {"max_steps": 10, "max_parallel_jobs": 1}

        });

        let report = validate_workflow_policy(&doc);

        assert!(!report.ok);

        assert!(report.errors.iter().any(|e| e.contains("cycle") || e.contains("cyclic")));

    }

}


