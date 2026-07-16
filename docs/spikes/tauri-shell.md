# Spike: Tauri packaging / shell

**ADR:** [0001-tauri-vs-electron.md](../adr/0001-tauri-vs-electron.md)

## Prototype

`apps/desktop` — Tauri 2, React, Vite, dialog plugin, CSP tightened from `null`.

## Windows notes

- Toolchain: `stable-x86_64-pc-windows-msvc` (`rustc 1.97.0` observed 2026-07-16).
- MSVC: Visual Studio 2022 Community + Build Tools present; `link.exe` / `cl.exe` on PATH.
- Ollama and Python reachable from spawned worker when PATH configured.
- App-local data: `%LOCALAPPDATA%\BrainFlow\` for session + SQLite indexes.
- Repo lives under OneDrive; prefer moderate `CARGO_BUILD_JOBS` if parallel `rustc` flakes.

## Exact Windows alpha build command

From repo root:

```powershell
npm install
# If prior rustc spawn/DLL flakes under parallel compile:
$env:CARGO_BUILD_JOBS = "2"
npm run build:desktop
# equivalent:
# npm run tauri -w desktop -- build
```

Artifacts (when successful) land under workspace `target/release/bundle/` (Cargo target-dir at repo root):

- `target/release/bundle/nsis/`
- `target/release/bundle/msi/`
- `target/release/desktop.exe`

## Packaging attempt (2026-07-16, earlier failure)

| Step | Result |
|------|--------|
| `npm run build` (Vite frontend, beforeBuildCommand) | **OK** — production web assets built |
| Frontend `apps/desktop/dist` footprint | **~5.75 MiB** (66 files); JS chunks ~2.0 MiB + ELK ~1.4 MiB (gzipped smaller) |
| `tauri build` / Rust release link | **FAILED** — `rustc` spawn errors during compile (`os error 3` / `STATUS_DLL_NOT_FOUND` `0xc0000135`) |
| Installer size (NSIS/MSI) | **Not measured** — bundle not produced |

**Diagnosis:** Host `rustc -vV` and a trivial `rustc main.rs` succeeded; toolchain `bin/` contained `rustc_driver-*.dll` + `std-*.dll`. Failure reproduced under heavy parallel release compile (environment flake / OneDrive contention), not missing app source. Mitigation: `CARGO_BUILD_JOBS=2` + clean retry.

## Packaging success (2026-07-16, consolidate re-run)

| Step | Result |
|------|--------|
| Toolchain probe | `rustc 1.97.0`, host `x86_64-pc-windows-msvc`, default rustup toolchain OK |
| `cargo test -p brainflow-sync` | **PASS** — 19 unit + 7 fixture tests |
| Vite `beforeBuildCommand` | **OK** — `dist` **5.75 MiB** (66 files) |
| `npm run build:desktop` (`CARGO_BUILD_JOBS=2`) | **OK** — release finished in ~10m 41s compile + WiX/NSIS |
| `desktop.exe` | **19.54 MiB** (20,489,216 bytes) |
| MSI | `BrainFlow_0.1.1_x64_en-US.msi` (was `0.1.0` pre-align; rebuild for tag match) |
| NSIS | `BrainFlow_0.1.1_x64-setup.exe` (was `0.1.0` pre-align; rebuild for tag match) |
| Cold-start / WebView2 timing | **Measured** 2026-07-16 — see § Cold-start below |
| Code signing | **Not applied** — unsigned local alpha only |

## Cold-start (time-to-window)

**Metric:** process start → visible `MainWindowHandle` (native HWND). This is **not** “UI fully interactive + Python sidecar ready.”

**Repro script** (Windows):

```powershell
npm run measure:cold-start
# or:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/measure-cold-start.ps1 -Samples 3
```

Requires `target/release/desktop.exe` from `npm run build:desktop`.

### Measured (2026-07-16, this Windows host)

Binary: `target/release/desktop.exe` (19.54 MiB). Host had WebView2 already installed; Ollama unrelated to this metric.

| Run | Samples (ms) | Notes |
|-----|--------------|-------|
| A (3× back-to-back) | **618**, 45, 47 | First launch after idle ~**618 ms**; immediate relaunches warm ~**45–47 ms** |
| B (1× after 5 s settle) | **91** | Warm OS / WebView2 cache |
| C (2× after ~8 s) | **90**, **64** | Warm cluster |

**Record for budgets:** cold-ish first sample **618 ms**; warm median ~**47–90 ms**. Treat consecutive sub-100 ms runs as warm, not cold.

## macOS / Linux packaging

| Platform | Status (2026-07-16) |
|----------|---------------------|
| Windows unsigned MSI/NSIS | **Done** on this host (sizes above) |
| macOS `.app` / DMG / notarization | **Not run** — no macOS CI runner or local Mac in this spike; prerequisites remain unchecked |
| Linux AppImage / deb | **Not run** — no Linux CI packaging job or cross-compile verification here |

Do not invent sizes for other OS. Cross-compile / CI matrix would be required before checking those boxes.

## Electron fallback criteria

Documented in [SPIKE_RESULTS.md](./SPIKE_RESULTS.md). Windows Tauri packaging feasibility is **proven** on this host (unsigned alpha bundles). Multi-OS packaging and Authenticode remain open before GA; **Windows cold-start time-to-window is recorded**.
