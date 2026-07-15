/**
 * Plugin SDK — capability manifests and allowlist types.
 * Runtime WASM sandbox lands later; v1 validates shape + permissions only.
 */

/** Capabilities a plugin may request. Anything else is rejected. */
export const PLUGIN_CAPABILITY_ALLOWLIST = [
  "ui.contribute",
  "vault.read",
  "vault.write.overlay",
  "workflow.read",
  "workflow.propose",
  "graph.read",
  "import.adapter",
  "export.adapter",
  "theme.contribute",
  "schema.extend",
  "network.none",
] as const;

export type PluginPermission = (typeof PLUGIN_CAPABILITY_ALLOWLIST)[number];

/** Capabilities deferred / denied in v1 even if listed in a manifesto draft */
export const PLUGIN_CAPABILITY_DENIED_V1 = [
  "shell.exec",
  "fs.arbitrary",
  "network.any",
  "dom.arbitrary",
  "native.code",
  "credentials.read",
  "publish.remote",
] as const;

export interface PluginManifest {
  /** Schema version for this manifest document */
  schema_version: 1;
  id: string;
  name: string;
  version: string;
  /** Semver range of BrainFlow host API this plugin targets */
  brainflow_api?: string;
  permissions: PluginPermission[];
  /** Declared UI / extension contribution points */
  contributions: {
    commands?: Array<{ id: string; title: string; hotkey?: string }>;
    views?: Array<{ id: string; title: string; placement?: "panel" | "drawer" }>;
    workflowNodes?: Array<{ type: string; title: string }>;
    importers?: Array<{ id: string; mime: string[] }>;
    exporters?: Array<{ id: string; format: string }>;
    themes?: Array<{ id: string; label: string }>;
    schemas?: Array<{ id: string; path: string }>;
  };
  /** Entry is WASM module path relative to package; not executed until sandbox ships */
  entry?: string;
  /** Signature placeholder — verified at install once marketplace lands */
  signature?: string;
}

export function isAllowedPermission(p: string): p is PluginPermission {
  return (PLUGIN_CAPABILITY_ALLOWLIST as readonly string[]).includes(p);
}

export function validateManifestShape(manifest: unknown): manifest is PluginManifest {
  if (!manifest || typeof manifest !== "object") return false;
  const m = manifest as Record<string, unknown>;
  if (
    m.schema_version !== 1 ||
    typeof m.id !== "string" ||
    typeof m.name !== "string" ||
    typeof m.version !== "string" ||
    !Array.isArray(m.permissions) ||
    typeof m.contributions !== "object" ||
    m.contributions === null
  ) {
    return false;
  }
  return (m.permissions as unknown[]).every(
    (p) => typeof p === "string" && isAllowedPermission(p),
  );
}

export function deniedCapabilities(requested: string[]): string[] {
  const denied = new Set(PLUGIN_CAPABILITY_DENIED_V1 as readonly string[]);
  return requested.filter((p) => denied.has(p) || !isAllowedPermission(p));
}
