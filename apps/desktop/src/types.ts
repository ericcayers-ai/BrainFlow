export type WorkflowNode = {
  id: string;
  type: string;
  title: string;
  permission_class?: string;
};

export type WorkflowEdge = {
  id: string;
  from: string;
  to: string;
  kind: string;
};

export type WorkflowIr = {
  schema_version: number;
  workflow_id: string;
  title: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  goal?: { statement?: string };
};
