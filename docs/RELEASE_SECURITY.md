# Release Security

Signing, updates, SBOM, and operational security for BrainFlow releases and model-registry channels.

---

## 1. Goals

- Users can verify app installers/updaters and model manifests.  
- Compromised channel can be revoked/rolled back.  
- Release metadata supports supply-chain review (SBOM, licenses).  

---

## 2. Application updates

| Control | Requirement |
|---------|-------------|
| Signing | Platform code signing (Authenticode / notarization / etc.) |
| Updater artifacts | Signed; verified before apply (Tauri updater model) |
| Channels | `dev` / `beta` / `stable` with promotion rules |
| Rollback | Previous version retained; UI path to roll back |
| Transport | HTTPS; certificate validation |

Never auto-apply updates that fail signature verification.

---

## 3. Model registry releases

- Signed manifests ([MODEL_REGISTRY.md](MODEL_REGISTRY.md))  
- Staged rollout → GA  
- Revocation list / revoke stage  
- Clients keep previous manifest digests  
- Weight downloads: checksum match required  

Key rotation: publish new key with dual-sign overlap window; document in release notes.

---

## 4. Build pipeline

- Reproducible release metadata (versions, commit SHA, builder id)  
- SBOM (CycloneDX or SPDX) attached to release  
- License scan gate — block forbidden licenses for distributed code  
- Secret scan on repo and release artifacts  
- Dependency pins; no floating versions in release builds  
- Least privilege on CI signing keys (HSM/OIDC cloud signing preferred when available)

---

## 5. Plugin (future)

- Signed manifests  
- Review + revocation  
- Capability transparency in UI before install  

---

## 6. Incident response (lightweight)

1. Revoke compromised channel artifacts / registry stage.  
2. Force clients to refuse bad signatures.  
3. Publish advisory with versions affected.  
4. Rotate keys if needed.  

---

## 7. Platform order

Windows signing path proven first (alpha → GA); macOS notarization and Linux packaging follow with parity gates ([ROADMAP.md](../ROADMAP.md) Phase 11).

---

## 8. Acceptance criteria

- AC-REL-01: Tampered updater package rejected in QA.  
- AC-REL-02: SBOM present on each stable release.  
- AC-REL-03: Registry revocation prevents Auto download of revoked digests.  
- AC-REL-04: Rollback installs previous stable from retained artifacts.  
- AC-REL-05: CI blocks release job if signature step skipped.
