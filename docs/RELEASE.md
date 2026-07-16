# Release governance

How BrainFlow ships desktop builds and operates update + model-registry channels. Complements [RELEASE_SECURITY.md](RELEASE_SECURITY.md), [VERSIONING.md](VERSIONING.md), [QA_LAUNCH.md](QA_LAUNCH.md).

---

## 1. Platform order

| Stage | Platform | Gate |
|-------|----------|------|
| Alpha → GA first | **Windows** | Authenticode; NVDA + keyboard checklist; packaging smoke |
| Follow | **macOS** | Notarization; VoiceOver parity; packaging smoke |
| Follow | **Linux** | Distro package/AppImage TBD; Orca optional |

Do not market macOS/Linux GA until packaging and assistive-technology parity for that OS pass ([ACCESSIBILITY.md](ACCESSIBILITY.md)). Continuous CI builds on all three remain welcome earlier.

---

## 2. Application updates (Tauri)

Requirements (mandatory for public channels):

- **Signed** updater artifacts verified before apply (Tauri updater model).  
- Channels: `dev` → `beta` → `stable` with promotion rules.  
- **Rollback:** retain previous stable installer/bundle; in-app path to reinstall previous.  
- HTTPS transport; certificate validation.  
- Never auto-apply updates that fail signature verification.

Windows signing path is proven first ([RELEASE_SECURITY.md](RELEASE_SECURITY.md) §7).

---

## 3. Model registry channels

Operate independently of app bitness, but **compatibility-test** each registry stage against supported app minors ([MODEL_REGISTRY.md](MODEL_REGISTRY.md)):

| Stage | Clients | Behavior |
|-------|---------|----------|
| `staged` | Internal / % rollout | New digests eligible for Auto only in cohort |
| `ga` | All | Default Auto refresh |
| `revoked` | All | Refuse download; keep last good |

**Rollback:** clients keep `previous/` manifests; operators promote prior digest to `ga` or push revocation. App and registry rollbacks are independent — a bad model catalog must not require uninstalling the app.

Key rotation: dual-sign overlap window; document in release notes.

---

## 4. Compatibility and deprecation

See [VERSIONING.md](VERSIONING.md). Summary:

- Portable vault / workflow IR / plugin API versions migrate with explicit migration functions.  
- Deprecate with: announce → UI warn → block Auto/new installs → revoke.  
- Do not silently break on-disk schemas in a patch release.

---

## 5. Mobile and web (explicitly deferred)

Mobile and browser clients are **out of scope for desktop GA**. Discovery may start only after:

1. Workflow IR + vault layout schemas are stable (semver minor-compatible),  
2. GitHub sync + conflict UX are production-ready,  
3. Plugin capability contracts are versioned and documented,

…and any mobile/web client must consume the **same portable data model**, not a second incompatible file format ([NON_GOALS.md](NON_GOALS.md), [DATA_MODEL.md](DATA_MODEL.md)).

---

## 6. Release train checklist

1. CI green (including a11y stub → axe; security scans promoted over time).  
2. [BETA_CHECKLIST.md](BETA_CHECKLIST.md) / [QA_LAUNCH.md](QA_LAUNCH.md) scenarios for the platform.  
3. SBOM + license + signature steps ([RELEASE_SECURITY.md](RELEASE_SECURITY.md)).  
4. Registry stage decision recorded.  
5. Known limitations published.  
6. Rollback owner on-call.

---

## 7. Code signing (required before public channels)

**Current alpha status (2026-07-16):** local NSIS/MSI/`desktop.exe` are **unsigned**. Do not claim signing or invent signature proofs.

### Windows (Authenticode) — required steps

1. Obtain an Authenticode code-signing certificate (org EV preferred for reputation; standard OV acceptable for internal alpha channels with SmartScreen caveats).  
2. Import cert into a release-only store or use cloud HSM / Azure Trusted Signing / SignPath / DigiCert KeyLocker (prefer keys never on build agents as files).  
3. After `npm run build:desktop`, sign **all** shipped PE artifacts:
   - `target/release/desktop.exe`
   - NSIS `BrainFlow_*_x64-setup.exe`
   - MSI `BrainFlow_*_x64_en-US.msi` (and embedded payloads per Tauri/WiX guidance)
4. Example local `signtool` (replace cert selection as your org requires):

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
  /n "YOUR_ORG_NAME" `
  target\release\desktop.exe `
  target\release\bundle\nsis\BrainFlow_0.1.1_x64-setup.exe `
  target\release\bundle\msi\BrainFlow_0.1.1_x64_en-US.msi
signtool verify /pa target\release\bundle\nsis\BrainFlow_0.1.1_x64-setup.exe
```

5. Wire the same step into CI release jobs; **fail the job if signature verification fails or the step is skipped** ([RELEASE_SECURITY.md](RELEASE_SECURITY.md) AC-REL-05).  
6. Configure Tauri updater with a signing keypair; ship only updater artifacts that verify before apply ([§2](#2-application-updates-tauri)).

### macOS / Linux (follow Windows)

- **macOS:** Developer ID Application signing + notarization (`notarytool`) before public DMG/`.app`. Not run in this repo yet.  
- **Linux:** Distro/AppImage signing TBD with packaging spike; no fake signatures.

Until the above succeeds in CI/QA, keep installers labeled **unsigned alpha**.

---

## 8. Acceptance criteria

- AC-RELGOV-01: Windows GA candidate meets AT + signing gates before marketing “1.0”.  
- AC-RELGOV-02: Failed signature blocks install in QA.  
- AC-RELGOV-03: Registry rollback restores previous selection without app reinstall.  
- AC-RELGOV-04: Docs state mobile/web deferred with shared-schema precondition.  
- AC-RELGOV-05: Docs list concrete Authenticode/notarization steps; alpha remains unsigned until executed.
