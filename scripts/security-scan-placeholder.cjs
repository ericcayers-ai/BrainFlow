#!/usr/bin/env node
/**
 * Security scan soft gates for CI.
 * Runs real npm audit + cargo audit when available; soft-fails so alpha CI stays green
 * until critical advisories are triaged. Promote to hard-fail before GA
 * (docs/RELEASE_SECURITY.md).
 */

const { execSync } = require("node:child_process");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const mode = process.argv[2] || "all";
const hard = process.env.BRAINFLOW_SECURITY_HARD === "1";

function run(label, cmd, { allowFail = !hard } = {}) {
  console.log(`\n[security] ▶ ${label}`);
  console.log(`[security] $ ${cmd}`);
  try {
    execSync(cmd, { cwd: root, stdio: "inherit", shell: true });
    console.log(`[security] PASS ${label}`);
    return true;
  } catch (e) {
    if (allowFail) {
      console.warn(`[security] SOFT-FAIL ${label}: ${e.message}`);
      return false;
    }
    console.error(`[security] FAIL ${label}`);
    process.exit(1);
  }
}

console.log(
  `[security] BrainFlow CI security scans (soft-fail unless BRAINFLOW_SECURITY_HARD=1)`,
);

if (mode === "npm" || mode === "all") {
  run("npm audit --audit-level=critical", "npm audit --omit=dev --audit-level=critical", {
    allowFail: !hard,
  });
}

if (mode === "cargo" || mode === "all") {
  // Install cargo-audit if missing, then run.
  try {
    execSync("cargo audit -V", { cwd: root, stdio: "pipe", shell: true });
  } catch {
    run("install cargo-audit", "cargo install cargo-audit --locked", { allowFail: true });
  }
  run("cargo audit", "cargo audit", { allowFail: !hard });
}

console.log("\n[security] scans complete — keep soft until critical baseline is clean, then harden for GA.");
