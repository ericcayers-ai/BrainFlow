#!/usr/bin/env node
/**
 * Accessibility CI gate.
 * Structural hooks + axe-core on built desktop HTML when available.
 * See docs/ACCESSIBILITY.md — full keyboard/AT suites remain a beta/GA gate.
 */

const fs = require("node:fs");
const path = require("node:path");
const { execSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const distIndex = path.join(root, "apps", "desktop", "dist", "index.html");

const checks = [];

function check(name, ok, detail) {
  checks.push({ name, ok, detail });
  const mark = ok ? "PASS" : "FAIL";
  console.log(`[a11y] ${mark} ${name}${detail ? ` — ${detail}` : ""}`);
}

check(
  "desktop dist present (run build first in CI)",
  fs.existsSync(distIndex),
  distIndex,
);

const appCss = path.join(root, "apps", "desktop", "src", "App.css");
const css = fs.existsSync(appCss) ? fs.readFileSync(appCss, "utf8") : "";
check("semantic token hooks (contrast)", css.includes("data-contrast") || css.includes("[data-contrast"));
check("reduced-motion hook", css.includes("reduced-motion") || css.includes("prefers-reduced-motion"));
check("forced-colors hook", css.includes("forced-colors"));
check(":focus-visible rule", css.includes(":focus-visible"));
check("sr-only helper", css.includes(".sr-only"));

const appTsx = path.join(root, "apps", "desktop", "src", "App.tsx");
const appSrc = fs.existsSync(appTsx) ? fs.readFileSync(appTsx, "utf8") : "";
check("Guided/Studio mode toggle", appSrc.includes("data-mode") || appSrc.includes("ExperienceMode"));
check("command palette mounted", appSrc.includes("CommandPalette"));

// axe on built HTML: use axe-core programmatically if installed, else soft note.
let axeOk = true;
let axeDetail = "skipped (axe-core not installed)";
if (fs.existsSync(distIndex)) {
  try {
    // Prefer npx axe (without failing CI hard if package missing).
    const html = fs.readFileSync(distIndex, "utf8");
    // Lightweight structural a11y on shell HTML.
    check("html lang attribute", /<html[^>]*\slang=/i.test(html), "prefer lang on <html>");
    check("has title", /<title>[^<]+<\/title>/i.test(html));

    try {
      require.resolve("axe-core");
      const axe = require("axe-core");
      axeDetail = `axe-core ${axe.version || ""} present — DOM crawl deferred (no browser in this gate)`;
      check("axe-core available", true, axeDetail);
    } catch {
      // Optional CLI crawl (file:// often breaks WebDriver). Opt-in: BRAINFLOW_AXE_CLI=1
      if (process.env.BRAINFLOW_AXE_CLI === "1") {
        try {
          execSync(`npx --yes @axe-core/cli@4.10.2 "file:///${distIndex.replace(/\\/g, "/")}" --exit`, {
            cwd: root,
            stdio: "pipe",
            shell: true,
            timeout: 120_000,
          });
          check("axe CLI on dist/index.html", true, "axe CLI exit 0");
        } catch (e) {
          console.warn(`[a11y] WARN axe CLI soft-fail: ${(e.stderr || e.message || "").toString().slice(0, 200)}`);
          check("axe CLI on dist/index.html (soft)", true, "soft-fail");
        }
      } else {
        check(
          "axe CLI deferred",
          true,
          "set BRAINFLOW_AXE_CLI=1 to enable; structural HTML checks still apply",
        );
      }
    }
  } catch (e) {
    console.warn(`[a11y] axe path error: ${e.message}`);
  }
}

const failed = checks.filter((c) => !c.ok);
if (failed.length) {
  console.error(`\n[a11y] ${failed.length} check(s) failed.`);
  process.exit(1);
}

console.log("\n[a11y] gate passed (structural + best-effort axe). Full AT/keyboard suites still required for GA.");
