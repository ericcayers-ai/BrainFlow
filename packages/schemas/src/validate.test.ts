import assert from "node:assert/strict";
import test from "node:test";
import {
  validateWorkflowIr,
  validateRunMetadata,
  validateDocumentBundle,
} from "./index.js";

const sampleWorkflow = {
  schema_version: 1,
  workflow_id: "11111111-1111-4111-8111-111111111111",
  title: "Slice demo",
  goal: { statement: "Produce a short study summary", constraints: [], success_metrics: [] },
  pins: {
    models: {
      planner: { provider: "ollama", name: "llama3.2:3b", digest: "sha256:demo" },
    },
    prompt_pack_version: "0.1.0",
  },
  nodes: [
    {
      id: "22222222-2222-4222-8222-222222222222",
      type: "summarize",
      title: "Summarize note",
      permission_class: "safe_overlay",
    },
    {
      id: "33333333-3333-4333-8333-333333333333",
      type: "write_artifact",
      title: "Write Markdown artifact",
      permission_class: "safe_overlay",
    },
  ],
  edges: [
    {
      id: "44444444-4444-4444-8444-444444444444",
      from: "22222222-2222-4222-8222-222222222222:out",
      to: "33333333-3333-4333-8333-333333333333:in",
      kind: "data",
    },
  ],
  budgets: {
    max_steps: 10,
    max_wall_time_ms: 600000,
    max_tokens: 8000,
    max_generated_files: 5,
    max_parallel_jobs: 1,
  },
  completion: {
    criteria: ["artifact_written"],
    terminal_statuses: ["succeeded", "failed", "cancelled", "needs_review"],
  },
  metadata: {
    created_at: "2026-07-15T00:00:00.000Z",
    created_by: "system",
    notes: "unit fixture",
  },
};

test("valid workflow IR passes", () => {
  const result = validateWorkflowIr(sampleWorkflow);
  assert.equal(result.ok, true, result.errors.join("; "));
});

test("missing schema_version fails", () => {
  const bad = { ...sampleWorkflow } as Record<string, unknown>;
  delete bad.schema_version;
  const result = validateWorkflowIr(bad);
  assert.equal(result.ok, false);
});

test("run metadata validates", () => {
  const result = validateRunMetadata({
    schema_version: 1,
    run_id: "55555555-5555-4555-8555-555555555555",
    workflow_id: sampleWorkflow.workflow_id,
    status: "succeeded",
    created_at: "2026-07-15T00:00:00.000Z",
    vault_relative_workflow_path: ".brainflow/workflows/demo.json",
    artifact_paths: [".brainflow/artifacts/w/r/summary.md"],
  });
  assert.equal(result.ok, true, result.errors.join("; "));
});

test("document bundle validates", () => {
  const result = validateDocumentBundle({
    schema_version: 1,
    bundle_id: "66666666-6666-4666-8666-666666666666",
    evidence_trust: "untrusted",
    source: {
      file_id: "77777777-7777-4777-8777-777777777777",
      path_mode: "link",
      content_hash:
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      mime_type: "text/markdown",
      size_bytes: 12,
    },
    metadata: {
      adapter_id: "markdown",
      adapter_version: "1.0.0",
    },
    segments: [
      {
        id: "s1",
        kind: "text",
        text: "hello",
        order: 0,
      },
    ],
    structure: {},
    images: [],
    transcripts: [],
    confidence: 1,
    warnings: [],
    errors: [],
    security: {
      quarantine_actions: [],
      active_content_flags: [],
    },
    provenance: {
      derived_from: [
        {
          file_id: "77777777-7777-4777-8777-777777777777",
          content_hash:
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        },
      ],
      analyzed_at: "2026-07-15T00:00:00.000Z",
      pipeline_version: "1.0.0",
    },
  });
  assert.equal(result.ok, true, result.errors.join("; "));
});
