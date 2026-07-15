import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ErrorObject } from "ajv";

const require = createRequire(import.meta.url);
// CJS interop under NodeNext
const Ajv2020 = require("ajv/dist/2020.js") as new (opts?: object) => {
  compile: (schema: object) => ((data: unknown) => boolean) & { errors?: ErrorObject[] | null };
};
const addFormats = require("ajv-formats") as (ajv: unknown) => void;

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

export const WORKFLOW_IR_SCHEMA_VERSION = 1 as const;
export const RUN_METADATA_SCHEMA_VERSION = 1 as const;
export const DOCUMENT_BUNDLE_SCHEMA_VERSION = 1 as const;
export const MODEL_REGISTRY_SCHEMA_VERSION = 1 as const;
export const GRAPH_SCHEMA_VERSION = 1 as const;

export function loadWorkflowIrSchema(): object {
  return JSON.parse(
    readFileSync(join(root, "workflow", "workflow-ir.schema.json"), "utf8"),
  ) as object;
}

export function loadRunMetadataSchema(): object {
  return JSON.parse(
    readFileSync(join(root, "run", "run-metadata.schema.json"), "utf8"),
  ) as object;
}

export function loadDocumentBundleSchema(): object {
  return JSON.parse(
    readFileSync(join(root, "ingestion", "document-bundle.schema.json"), "utf8"),
  ) as object;
}

export function loadModelRegistrySchema(): object {
  return JSON.parse(
    readFileSync(join(root, "model-registry", "model-registry.schema.json"), "utf8"),
  ) as object;
}

export function loadGraphSchema(): object {
  return JSON.parse(
    readFileSync(join(root, "graph", "graph.schema.json"), "utf8"),
  ) as object;
}

export function loadGraphPatchSchema(): object {
  return JSON.parse(
    readFileSync(join(root, "graph", "graph-patch.schema.json"), "utf8"),
  ) as object;
}

export function createValidator() {
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  const validateWorkflow = ajv.compile(loadWorkflowIrSchema());
  const validateRun = ajv.compile(loadRunMetadataSchema());
  const validateBundle = ajv.compile(loadDocumentBundleSchema());
  const validateRegistry = ajv.compile(loadModelRegistrySchema());
  const validateGraph = ajv.compile(loadGraphSchema());
  const validateGraphPatch = ajv.compile(loadGraphPatchSchema());
  return {
    ajv,
    validateWorkflow,
    validateRun,
    validateBundle,
    validateRegistry,
    validateGraph,
    validateGraphPatch,
  };
}

export function validateWorkflowIr(data: unknown): {
  ok: boolean;
  errors: string[];
} {
  const { validateWorkflow } = createValidator();
  const ok = validateWorkflow(data);
  return {
    ok: Boolean(ok),
    errors: (validateWorkflow.errors ?? []).map(
      (e: ErrorObject) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`,
    ),
  };
}

export function validateRunMetadata(data: unknown): {
  ok: boolean;
  errors: string[];
} {
  const { validateRun } = createValidator();
  const ok = validateRun(data);
  return {
    ok: Boolean(ok),
    errors: (validateRun.errors ?? []).map(
      (e: ErrorObject) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`,
    ),
  };
}

export function validateDocumentBundle(data: unknown): {
  ok: boolean;
  errors: string[];
} {
  const { validateBundle } = createValidator();
  const ok = validateBundle(data);
  return {
    ok: Boolean(ok),
    errors: (validateBundle.errors ?? []).map(
      (e: ErrorObject) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`,
    ),
  };
}

export function validateGraph(data: unknown): {
  ok: boolean;
  errors: string[];
} {
  const { validateGraph: v } = createValidator();
  const ok = v(data);
  return {
    ok: Boolean(ok),
    errors: (v.errors ?? []).map(
      (e: ErrorObject) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`,
    ),
  };
}

export function validateGraphPatch(data: unknown): {
  ok: boolean;
  errors: string[];
} {
  const { validateGraphPatch: v } = createValidator();
  const ok = v(data);
  return {
    ok: Boolean(ok),
    errors: (v.errors ?? []).map(
      (e: ErrorObject) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`,
    ),
  };
}

export function validateModelRegistry(data: unknown): {
  ok: boolean;
  errors: string[];
} {
  const { validateRegistry } = createValidator();
  const ok = validateRegistry(data);
  return {
    ok: Boolean(ok),
    errors: (validateRegistry.errors ?? []).map(
      (e: ErrorObject) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`,
    ),
  };
}
