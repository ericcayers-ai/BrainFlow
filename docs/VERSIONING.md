# Versioning, compatibility, and deprecation

Semver-oriented policy for BrainFlow app builds, portable schemas, plugin API, and model registry manifests.

---

## 1. Version surfaces

| Surface | Location | Scheme |
|---------|----------|--------|
| Application | installer / Tauri `version` | Semver `MAJOR.MINOR.PATCH` |
| Workflow IR | `packages/schemas/workflow` | Schema `schema_version` integer + migrations |
| Run metadata | `packages/schemas/run` | Same |
| Vault layout | `.brainflow/vault.json` + folder contracts | Documented layout version |
| Plugin host API | `@brainflow/plugin-sdk` / manifest `brainflow_api` | Semver range |
| Model registry | signed manifest `manifest_version` | Integer + digest chain |

App **patch** releases must not require vault data migrations. **Minor** may add optional fields. **Major** may require migrations with in-app upgrade UI and rollback notes.

---

## 2. Compatibility promise

- Older portable vaults open after forward migrations; migrations are tested and reversible where feasible ([DATA_MODEL.md](DATA_MODEL.md)).  
- Indexes are rebuildable — deleting local app data is always safe.  
- Plugin manifests declaring unsupported capabilities or API ranges fail closed at install.  
- Model digests are immutable; “upgrades” are new digests, never silent retagging.

---

## 3. Deprecation policy

For schemas, node types, plugin capabilities, registry models, and provider adapters:

1. **Announce** in release notes + docs with sunset target (minimum one minor).  
2. **Warn** in UI when loading deprecated constructs.  
3. **Block Auto** / new usage while still loading existing user data if safe.  
4. **Revoke** only after migration tooling exists or explicit user acknowledgement.

Security-driven emergency revocation (compromised model, broken signature) may skip to step 4 with advisory ([RELEASE_SECURITY.md](RELEASE_SECURITY.md)).

---

## 4. Channels vs versions

`dev` / `beta` / `stable` are **channels**, not semver prerelease substitutes. A build can be `1.2.0` on `beta` then promoted to `stable` without changing the version string, or tag `1.2.0-beta.N` when clearer for QA — pick one convention per release train and document it in notes.

---

## 5. Mobile/web precondition

Shared schema stability (this document + [WORKFLOW_IR.md](WORKFLOW_IR.md) + [DATA_MODEL.md](DATA_MODEL.md)) is a **prerequisite** for mobile/web clients ([RELEASE.md](RELEASE.md) §5).

---

## 6. Acceptance criteria

- AC-VER-01: Every persisted schema bump has a migration function and test.  
- AC-VER-02: Patch release checklist includes “no breaking vault layout change.”  
- AC-VER-03: Deprecated capability remains loadable until sunset unless security revoke.
