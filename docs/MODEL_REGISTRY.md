# Model Registry

Signed, versioned catalog of models and scores used by [MODEL_SELECTION.md](MODEL_SELECTION.md). Governance must prevent blind trust of scraped leaderboards.

---

## 1. Registry purpose

Provide immutable model identifiers, capability metadata, fit formulas, and provenance-backed quality signals that clients can verify offline after download.

---

## 2. Manifest structure

```text
manifest_version
issued_at
issuer
models[]
  id
  display_name
  source (publisher / channel)
  release_date
  digests[]          # immutable content digests per quantization artifact
  quantizations[]
  parameter_count / MoE shape
  context_lengths[]
  modalities[]       # text, vision, audio, …
  capabilities       # tools, json_schema, embeddings, …
  license
  known_security_issues[]
  memory_formula     # versioned formula id + params
  quality_scores[]   # each with provenance
  benchmark_refs[]
signature            # over canonical bytes
previous_manifest_digest
rollout_stage        # staged | ga | revoked
```

Clients verify signature against pinned public keys shipped with the app (with key rotation procedure in [RELEASE_SECURITY.md](RELEASE_SECURITY.md)).

---

## 3. Signing and trust

| Control | Requirement |
|---------|-------------|
| Signature | Ed25519 or equivalent; algorithm agility documented |
| Channel | HTTPS + pinning or equivalent transparency |
| Rollback | Clients keep N previous manifests; operator can mark revoke |
| Staged rollout | Percentage / cohort before GA |
| Compromise | Revocation list; force re-fetch; pause Auto downloads |

**Never** execute code from model repositories. Verify weight checksums; reject unsafe pickle / remote-code-required artifacts unless explicitly out of policy (default reject).

---

## 4. Score provenance

Each `quality_scores[]` entry must include:

- Metric name + version  
- Dataset / eval suite id  
- Job id / reproducible parameters  
- Model digest evaluated  
- Timestamp  
- Hardware class used (if score is hardware-sensitive)

Do not ingest an unsigned third-party board as authoritative without re-running or independently verifying under BrainFlow eval jobs.

---

## 5. Client behavior

1. Refresh on demand and configurable schedule.  
2. On signature failure → keep last good; warn; disable Auto download of new weights.  
3. Offline → operate on cache; selection still applies capability + local probes.  
4. Surface license text / summary before download.  
5. Disk budget gate before pull.

---

## 6. Local cache layout

Under app data (not vault):

```text
model-registry/
  current.json
  previous/
  keys/   # optional mirrored keyring metadata
```

Vault portable files must not store registry blobs.

### Schema and bundled snapshot

| Artifact | Path |
|----------|------|
| JSON Schema | `packages/schemas/model-registry/model-registry.schema.json` |
| Dev signed fixture | `packages/schemas/model-registry/fixtures/registry.v1.json` |
| Pinned keys metadata | `packages/schemas/model-registry/keys/pinned-keys.json` |
| Worker cache (runtime) | `%LOCALAPPDATA%\BrainFlow\model-registry\` (or `$BRAINFLOW_APP_DATA`) |

---

## 6b. Update / sign / rollback (operator + client)

### Sign (issuer)

1. Build canonical JSON (`sort_keys`, skip `signature` field).  
2. Compute `content_digest = sha256:…`.  
3. Attach signature:
   - **Production:** `alg=ed25519`, `key_id`, hex signature over canonical bytes (`cryptography` / OpenSSL).  
   - **Dev/CI:** `alg=bf-hmac-v1` with `brainflow-dev` HMAC (fixture key; not for Auto production downloads).  
4. Set `previous_manifest_digest` to the prior GA digest.  
5. Set `rollout_stage` to `staged` then promote to `ga`.

Regenerate the repo fixture:

```bash
python packages/schemas/model-registry/fixtures/_gen_registry.py
```

### Update (client)

1. RPC `registry.load` with `refresh=true` boots from bundled fixture into app-data cache when empty.  
2. `registry.install` verifies signature; on success rotates `current.json` → `previous/<stamp>-<digest>.json`.  
3. On verify failure: keep last good cache; surface warning; do not Auto-download new weights.

### Rollback (client)

1. RPC `registry.rollback` restores the newest file under `previous/`.  
2. Selection continues offline against the restored snapshot.  
3. Operators may also push `rollout_stage: revoked` on a poisoned manifest; clients refuse Auto install.

---

## 7. Operator / governance process

- Reproducible evaluation jobs for BrainFlow suites.  
- Human review for security issues and license changes.  
- Deprecation policy: announce → warn in UI → block Auto → revoke ([VERSIONING.md](VERSIONING.md)).  
- Compatibility testing with app releases ([RELEASE.md](RELEASE.md), [RELEASE_SECURITY.md](RELEASE_SECURITY.md)).  
- Release/rollback **channels**: `staged` → `ga`, with `revoked` and client `previous/` cache for instant rollback without app reinstall.

---

## 8. Acceptance criteria

- AC-MR-01: Tampered manifest fails verification in CI fixture.  
- AC-MR-02: Rollback restores previous manifest and selection still functions.  
- AC-MR-03: Model with `remote_code_required` not eligible by default.  
- AC-MR-04: Digest mismatch on download aborts install and notifies user.  
- AC-MR-05: Offline mode uses cached manifest without network.
