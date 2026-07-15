#!/usr/bin/env node
/**
 * Fuzz entrypoint stub — enumerates harness directories and exits 0.
 * Wire cargo-fuzz / atheris binaries here when ingestion and IR parsers grow.
 */

const fs = require("node:fs");
const path = require("node:path");

const fuzzRoot = path.resolve(__dirname, "..", "tests", "fuzz");
const expected = ["workflow_ir", "markdown", "ipc", "archives"];

let ok = true;
for (const dir of expected) {
  const p = path.join(fuzzRoot, dir);
  const has = fs.existsSync(p);
  console.log(`[fuzz] ${has ? "OK" : "MISSING"} ${dir}`);
  if (!has) ok = false;
}

if (!ok) {
  console.error("[fuzz] missing harness directories");
  process.exit(1);
}

console.log("[fuzz] entrypoints present (no corpus run in stub mode)");
