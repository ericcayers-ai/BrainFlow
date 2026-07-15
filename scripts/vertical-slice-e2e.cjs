#!/usr/bin/env node
/**
 * Vertical-slice E2E driver: runs tests/e2e/test_vertical_slice.py with the
 * ai-worker venv when present. Exercise open vault → save → intake → LLM
 * generate (fail-closed) → .brainflow artifact → session reopen.
 */
const { execSync, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const worker = path.join(root, "services", "ai-worker");
const winPy = path.join(worker, ".venv", "Scripts", "python.exe");
const nixPy = path.join(worker, ".venv", "bin", "python");
const py = fs.existsSync(winPy) ? winPy : fs.existsSync(nixPy) ? nixPy : "python";

const args = [
  "-m",
  "pytest",
  path.join(root, "tests", "e2e", "test_vertical_slice.py"),
  "-v",
  "--tb=short",
];

console.log(`[e2e] ▶ vertical-slice with ${py}`);
const r = spawnSync(py, args, {
  cwd: worker,
  stdio: "inherit",
  env: {
    ...process.env,
    PYTHONPATH: [worker, process.env.PYTHONPATH || ""].filter(Boolean).join(path.delimiter),
  },
  shell: false,
});
if (r.status !== 0) {
  process.exit(r.status || 1);
}
console.log("[e2e] vertical-slice green.");
