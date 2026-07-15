#!/usr/bin/env node
/**
 * Vertical-slice smoke: worker unit tests + core Rust crates + desktop typecheck.
 * Intended as a single green-path gate for CI (does not require full tauri build).
 */

const { execSync } = require("node:child_process");
const path = require("node:path");

const root = path.resolve(__dirname, "..");

function run(label, cmd, opts = {}) {
  console.log(`\n[smoke] ▶ ${label}`);
  console.log(`[smoke] $ ${cmd}`);
  execSync(cmd, {
    cwd: opts.cwd || root,
    stdio: "inherit",
    shell: true,
    env: process.env,
  });
  console.log(`[smoke] PASS ${label}`);
}

console.log("[smoke] BrainFlow vertical-slice smoke");

run("Python worker pytest", "pytest -q", {
  cwd: path.join(root, "services", "ai-worker"),
});

run(
  "Rust core crates",
  "cargo test -p brainflow-vault -p brainflow-storage -p brainflow-policy -p brainflow-graph -p brainflow-sync -p brainflow-app-core",
);

run("Desktop typecheck", "npm run typecheck -w desktop");

console.log("\n[smoke] vertical-slice smoke green.");
