# Security

Engineering controls implementing [THREAT_MODEL.md](THREAT_MODEL.md).

---

## 1. Application shell

- Tauri **least-privilege capabilities** per window  
- Strict **CSP**; no inline arbitrary script from vault content  
- Scoped filesystem grants: vault roots + user-linked sources only  
- Disable active scripts and remote resource loading in rendered Markdown/HTML by default  
- Isolate web previews; sandbox web viewer  

---

## 2. Content sanitization

- Markdown/HTML sanitizer deny-list for scripts, handlers, `javascript:`  
- No `file://` navigation from content  
- Math/callouts/embeds rendered via safe paths  
- PDF/Office parsing in worker quarantine — never execute macros  

---

## 3. IPC and worker

- Private inherited pipe / platform IPC — **not** fixed unauthenticated localhost port ([adr/0002-sidecar-transport.md](adr/0002-sidecar-transport.md))  
- Schema validation every message  
- Worker cannot access OS keychain directly; secrets injected narrowly or Git handled in core  
- Resource limits on ingestion jobs  

---

## 4. LLM / tools

- Planner: **no** FS/Git/shell/network/credential/publish/delete tools  
- Tools only via policy engine: path scopes, rate limits, arg validation, approval classes  
- Structured output + schema validation only  
- Block SSRF: no private-network / link-local / metadata endpoints via provider tools  
- Cloud requests: TLS for non-loopback; endpoint allowlists; spend/token limits  

---

## 5. Models and registry

- Verify checksums and **signed** registry manifests  
- Surface licenses; reject remote-code / unsafe pickle by default  
- Never execute model-repo code  

---

## 6. Sync and secrets

- Tokens in OS credential store  
- Minimal GitHub scopes  
- Pre-commit secret scanning  
- No force-push automation  
- Credentials never into portable vault or logs  

---

## 7. Plugins

- Signed manifests; explicit capabilities  
- Sandboxed WASM; no arbitrary DOM/native in v1  
- Future marketplace: review + revocation  

---

## 8. Supply chain / build

- Dependency pinning via lockfiles  
- Controlled update PRs  
- SBOM generation for releases  
- Secret scanning + license scanning in CI  
- Reproducible release metadata where feasible  

---

## 9. Reliability that is security-relevant

- Atomic writes; SQLite WAL  
- Snapshots; migrations with rollback  
- Disk-space preflight  
- Crash consistency tests; backup/restore drills  

---

## 10. Acceptance criteria

- AC-SEC-01: Capability grant tests prove UI cannot read outside scopes.  
- AC-SEC-02: XSS corpus in Markdown shows zero script execution.  
- AC-SEC-03: Worker binding public TCP port fails CI policy check.  
- AC-SEC-04: Unapproved `shell` tool invoke throws and audits.  
- AC-SEC-05: Registry/update signature failures block install.
