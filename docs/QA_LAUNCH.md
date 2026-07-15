# QA launch matrix

Operational companion to [BETA_CHECKLIST.md](BETA_CHECKLIST.md) for pre-beta and pre-GA launches.

---

## 1. Platforms

| Order | OS | Packaging | AT gate |
|-------|-----|-----------|---------|
| 1 | Windows 10/11 | MSI/NSIS (Tauri) + Authenticode | NVDA + keyboard |
| 2 | macOS | DMG + notarization | VoiceOver |
| 3 | Linux | AppImage/deb ( TBD ) | Orca smoke optional |

Mobile/web clients are **out of launch scope** until portable schemas stabilize ([RELEASE.md](RELEASE.md)).

---

## 2. Domain × device matrix (minimum)

| Tester domain | Device tier | Vault size | Sync |
|---------------|-------------|------------|------|
| Student | Low-tier Windows laptop | ≤500 notes | Optional later |
| Researcher | Mid Windows / macOS | 2k–10k notes | Private GitHub |
| Educator | Mid Windows | Mixed imports | Optional |
| PM / ops | Mid Windows | Project pack | Multi-device if available |
| Engineer | High (GPU) | Code + docs | GitHub |
| A11y | Windows + NVDA | Small | N/A |

---

## 3. Build flavors

| Channel | Audience | Telemetry |
|---------|----------|-----------|
| `dev` | Internal | Off |
| `beta` | Closed cohort | Opt-in crash only |
| `stable` | GA | Opt-in crash only |

---

## 4. Launch day checklist

- [ ] SBOM attached; license scan clean  
- [ ] Signature verification demo recorded  
- [ ] Model registry previous manifest retained for rollback  
- [ ] Support channel + known-limitations URL live  
- [ ] Rollback owner named on-call  

See [RELEASE.md](RELEASE.md) and [RELEASE_SECURITY.md](RELEASE_SECURITY.md).
