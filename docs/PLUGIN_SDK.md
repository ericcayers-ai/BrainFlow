# Plugin SDK (capability manifests)

BrainFlow does **not** claim Obsidian community-plugin API compatibility in v1. Extensions use BrainFlow’s own sandboxed contract: **signed manifests + explicit capabilities + WASM** (runtime sandbox ships after the foundation slice).

Package: `@brainflow/plugin-sdk` · Examples: [packages/plugin-sdk/examples/](../packages/plugin-sdk/examples/)

---

## 1. Capability allowlist (v1)

| Capability | Meaning |
|------------|---------|
| `ui.contribute` | Declarative commands, views, panels |
| `vault.read` | Read vault-relative paths already granted to the host |
| `vault.write.overlay` | Write only under `.brainflow/` overlays (not source files) |
| `workflow.read` | Read workflow IR / run metadata |
| `workflow.propose` | Propose schema-valid patches for user approval |
| `graph.read` | Read graph projections |
| `import.adapter` | Register an ingestion adapter (still sandboxed) |
| `export.adapter` | Register an exporter (local files; remote publish separate) |
| `theme.contribute` | CSS token packs / theme metadata |
| `schema.extend` | Contribute JSON Schema fragments for validation |
| `network.none` | Explicit denial of network (recommended default) |

### Denied in v1 (always reject)

`shell.exec`, `fs.arbitrary`, `network.any`, `dom.arbitrary`, `native.code`, `credentials.read`, `publish.remote`

Remote publish must go through the host approval gate ([PUBLISHING.md](PUBLISHING.md)), not a plugin capability.

---

## 2. Manifest shape

See TypeScript `PluginManifest` and:

- [manifest.example.json](../packages/plugin-sdk/examples/manifest.example.json)
- [theme-manifest.example.json](../packages/plugin-sdk/examples/theme-manifest.example.json)

Validation helper: `validateManifestShape` / `deniedCapabilities`.

---

## 3. Contribution points (declarative first)

Commands, views, workflow node types, importers, exporters, themes, schemas. No arbitrary DOM or native code until a reviewed marketplace + revocation path exists ([SECURITY.md](SECURITY.md)).

---

## 4. Signing and marketplace (later)

Install will require signed manifests and a host verification step. Revocation list will mirror [RELEASE_SECURITY.md](RELEASE_SECURITY.md) patterns. Until then, first-party / developer sideload for testing only.

---

## 5. Acceptance criteria

- AC-PLG-01: Manifest with unknown permission fails validation.  
- AC-PLG-02: Denied-v1 capabilities rejected even if declared.  
- AC-PLG-03: Example manifests in repo validate under `validateManifestShape`.
