import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import type { ErrorObject } from "ajv";
import graphPatchSchema from "../../../../packages/schemas/graph/graph-patch.schema.json" with {
  type: "json",
};
import type { GraphPatch, GraphPatchOp } from "./model";

const ajv = new Ajv2020({ allErrors: true, strict: false });
// ajv-formats typings lag Ajv2020; cast is intentional for draft-2020 instance.
addFormats(ajv as unknown as Parameters<typeof addFormats>[0]);
const validate = ajv.compile(graphPatchSchema as object);

export type PatchParseResult =
  | { ok: true; patch: GraphPatch }
  | { ok: false; error: string };

const OPS = new Set([
  "add_node",
  "remove_node",
  "update_node",
  "add_edge",
  "remove_edge",
]);

function formatErrors(errors: ErrorObject[] | null | undefined): string {
  if (!errors?.length) return "invalid graph patch";
  return errors
    .map((e) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`)
    .join("; ");
}

/**
 * Schema-valid only: reject anything that fails JSON Schema draft 2020-12
 * (`packages/schemas/graph/graph-patch.schema.json`) before review/apply.
 */
export function parseGraphPatch(raw: unknown): PatchParseResult {
  if (raw == null || typeof raw !== "object") {
    return { ok: false, error: "patch must be an object" };
  }
  const ok = validate(raw);
  if (!ok) {
    return { ok: false, error: formatErrors(validate.errors) };
  }
  const patch = raw as GraphPatch;
  for (const op of patch.ops) {
    if (!OPS.has((op as GraphPatchOp).op)) {
      return { ok: false, error: `unknown patch op: ${(op as { op?: string }).op}` };
    }
    if (op.op === "add_node" && (!op.node || typeof op.node !== "object")) {
      return { ok: false, error: "add_node requires node object" };
    }
    if (op.op === "add_edge" && (!op.edge || typeof op.edge !== "object")) {
      return { ok: false, error: "add_edge requires edge object" };
    }
    if (
      (op.op === "remove_node" || op.op === "update_node" || op.op === "remove_edge") &&
      typeof op.id !== "string"
    ) {
      return { ok: false, error: `${op.op} requires id` };
    }
  }
  return { ok: true, patch };
}
