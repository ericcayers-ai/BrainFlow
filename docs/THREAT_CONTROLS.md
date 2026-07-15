# Threat model → control checklist

Maps [THREAT_MODEL.md](THREAT_MODEL.md) abuse cases and STRIDE rows to concrete controls and verification. Use before closed beta and GA.

| ID | Threat / abuse case | Primary controls | Verification |
|----|---------------------|------------------|--------------|
| TC-01 | Malicious Markdown/HTML (script, remote image) | Sanitizer; CSP; no remote load default ([SECURITY.md](SECURITY.md) §1–2) | XSS corpus; CI content fixtures |
| TC-02 | Prompt injection (direct) | Delimited untrusted evidence; planner tool deny ([AI_SAFETY_AND_AGENCY.md](AI_SAFETY_AND_AGENCY.md)) | [tests/evals/prompt_injection](../tests/evals/prompt_injection/) |
| TC-03 | Indirect injection via documents / retrieval | Same + label evidence; retrieval not authority | `indirect_document`, `poisoned_retrieval` fixtures |
| TC-04 | Archive bomb / resource exhaustion | Worker quarantine; decompression/page/time limits ([FILE_INGESTION.md](FILE_INGESTION.md)) | Fuzz `tests/fuzz/archives`; limit unit tests |
| TC-05 | Malicious workflow JSON from sync | Schema + policy reject before exec ([WORKFLOW_IR.md](WORKFLOW_IR.md)) | Policy crate tests; fuzz `workflow_ir` |
| TC-06 | Tampered app update | Signed Tauri updater ([RELEASE_SECURITY.md](RELEASE_SECURITY.md)) | AC-REL-01 tamper reject |
| TC-07 | Tampered model registry / weights | Signed manifests; checksum; reject pickle/remote-code ([MODEL_REGISTRY.md](MODEL_REGISTRY.md)) | AC-MR-01–04 |
| TC-08 | Plugin undeclared / excessive capability | Allowlist validation ([PLUGIN_SDK.md](PLUGIN_SDK.md)) | `deniedCapabilities` unit + install deny |
| TC-09 | Public IPC / localhost bridge | Private inherited pipe only ([adr/0002](adr/0002-sidecar-transport.md)) | AC-SEC-03 CI policy |
| TC-10 | SSRF via provider tools | Block private/link-local/`file://` ([SECURITY.md](SECURITY.md) §4) | Tool policy tests |
| TC-11 | Credential leak in logs / Git | Redaction ([PRIVACY.md](PRIVACY.md)); pre-commit secret scan; OS keychain | Redaction unit tests; gitleaks in CI (placeholder) |
| TC-12 | Excessive agency / runaway loops | Budgets, retries, terminal status ([WORKFLOW_IR.md](WORKFLOW_IR.md)) | `runaway_loop` fixture; executor tests |
| TC-13 | Confused deputy (worker ambient creds) | Git in Rust core; narrow secret injection | Architecture review; contract tests |
| TC-14 | Supply chain (deps / SBOM) | Lockfiles; SBOM; license/secret scan ([RELEASE_SECURITY.md](RELEASE_SECURITY.md)) | CI placeholders → blocking at GA |
| TC-15 | Remote publish without consent | Approval gate ([PUBLISHING.md](PUBLISHING.md)) | AC-PUB-01 |
| TC-16 | Crash telemetry oversharing | Opt-in only; redaction ([CRASH_REPORTING.md](CRASH_REPORTING.md)) | AC-PRV-01; consent UI |

## Sign-off

| Gate | Owner | Date | Notes |
|------|-------|------|-------|
| Pre-beta | Security + eng | | All TC rows assigned; critical gaps tracked |
| Pre-GA | Security + eng | | OWASP LLM orientation + desktop review done |

Related: [BETA_CHECKLIST.md](BETA_CHECKLIST.md) · [QA_STRATEGY.md](QA_STRATEGY.md)
