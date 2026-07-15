import assert from "node:assert/strict";
import test from "node:test";
import { parseGraphPatch } from "./patchValidate.ts";

test("accepts schema-valid patch", () => {
  const r = parseGraphPatch({
    schema_version: 1,
    summary: "ok",
    ops: [
      {
        op: "add_node",
        node: {
          id: "11111111-1111-4111-8111-111111111111",
          type: "Question",
          label: "Q",
        },
      },
    ],
  });
  assert.equal(r.ok, true);
});

test("rejects wrong schema_version", () => {
  const r = parseGraphPatch({ schema_version: 2, ops: [] });
  assert.equal(r.ok, false);
});

test("rejects unknown op via schema enum", () => {
  const r = parseGraphPatch({
    schema_version: 1,
    ops: [{ op: "explode_graph" }],
  });
  assert.equal(r.ok, false);
});

test("rejects non-object", () => {
  assert.equal(parseGraphPatch("nope").ok, false);
});

test("rejects too many ops", () => {
  const ops = Array.from({ length: 51 }, () => ({
    op: "remove_node",
    id: "11111111-1111-4111-8111-111111111111",
  }));
  const r = parseGraphPatch({ schema_version: 1, ops });
  assert.equal(r.ok, false);
});
