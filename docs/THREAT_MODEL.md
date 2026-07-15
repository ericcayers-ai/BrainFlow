# Threat Model

Pre-beta baseline. Update when architecture changes. Controls live in [SECURITY.md](SECURITY.md), [PRIVACY.md](PRIVACY.md), [RELEASE_SECURITY.md](RELEASE_SECURITY.md), [AI_SAFETY_AND_AGENCY.md](AI_SAFETY_AND_AGENCY.md).

---

## 1. Assets

| Asset | Sensitivity |
|-------|-------------|
| User vault Markdown & attachments | High |
| Linked source files | High |
| Workflow IR / artifacts / provenance | High |
| GitHub tokens / provider API keys | Critical |
| Model registry trust anchors | Critical |
| Local indexes / embeddings | Medium–High (may embed sensitive text) |
| Telemetry/crash (if enabled) | Medium |

---

## 2. Trust boundaries

```text
[WebView UI] --IPC--> [Rust core] --IPC--> [Python worker]
      |                   |                     |
      |                   +-- OS keychain        +-- parsers (untrusted files)
      |                   +-- Git remote         +-- LLM providers
      +-- rendered Markdown (untrusted)
```

---

## 3. Adversaries

- Malicious documents (PDF/Office/HTML/Markdown)  
- Prompt injection (direct + indirect via retrieved/evidence text)  
- Compromised plugin / manifest  
- Tampered model weights or registry manifests  
- Malicious or MITM provider endpoints  
- Stolen Git credentials / repo collaborators  
- Compromised update infrastructure  
- Local malware with user privileges (partial; OS-level limits)

---

## 4. STRIDE-style threats (selected)

| Threat | Example | Mitigation summary |
|--------|---------|-------------------|
| Spoofing | Fake update or registry | Signed updates + signed manifests |
| Tampering | Rewrite source via agent | Immutable sources; approval gates; policy |
| Repudiation | Hidden AI actions | Immutable audit trail |
| Info disclosure | Exfil via LLM/cloud | Redaction, previews, allowlists, opt-in telemetry |
| DoS | Zip bomb / token burn | Resource limits, budgets |
| Elevation | Plugin/native code exec | WASM sandbox; no arbitrary native plugins v1 |
| Prompt injection | “Ignore policy, delete…” | Delimited untrusted evidence; no FS tools for planner |
| SSRF | `file://` / metadata IP via tools | Block private network / file schemes in tools |
| Confused deputy | Worker ambient creds | Per-job least privilege; Git in core |
| Supply chain | Dependency / model pickle | Pinning, SBOM, checksums, reject remote code |

---

## 5. Abuse cases (must have tests)

1. Markdown/HTML with script / remote image → sanitized, no active content.  
2. Document text instructing model to exfiltrate vault → blocked by policy + eval.  
3. Archive bomb → resource limit.  
4. Malicious workflow JSON in synced repo → schema/policy reject before exec.  
5. Tampered registry signature → reject.  
6. Plugin requesting undeclared capability → deny.  
7. Localhost bridge attacker (if misconfigured IPC) → private IPC makes this N/A; regression test against binding public ports.

---

## 6. Residual risks (accepted with communication)

- Private GitHub content readable by GitHub & collaborators  
- Local disk encryption is OS responsibility  
- User-approved shell/publish actions can harm  
- Local malware with user rights can read vault files  

---

## 7. Review cadence

Threat model review before closed beta and GA; on major IPC/plugin/sync changes. Complete OWASP LLM verification orientation + desktop security review before GA ([QA_STRATEGY.md](QA_STRATEGY.md)).

Control mapping checklist: [THREAT_CONTROLS.md](THREAT_CONTROLS.md).
