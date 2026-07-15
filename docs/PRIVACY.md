# Privacy

Data handling commitments for BrainFlow. Related: [DATA_MODEL.md](DATA_MODEL.md) · [SECURITY.md](SECURITY.md) · [PRODUCT_SPEC.md](PRODUCT_SPEC.md)

---

## 1. Principles

1. **Local-first** — vault content stays on device unless user syncs or calls cloud providers.  
2. **User-owned portable files** — Markdown and `.brainflow` portable data are user data.  
3. **Minimize** — no surplus telemetry; redaction by default in logs.  
4. **Honest cloud** — private GitHub ≠ E2E encryption; cloud LLM sends prompts/evidence as disclosed.  
5. **Consent** — cloud model use, telemetry, publishing require clear consent.

---

## 2. Data categories

| Category | Storage | Leaves device? |
|----------|---------|----------------|
| Notes, artifacts, workflows | Vault | If user enables GitHub sync |
| Linked sources | Original paths | Not uploaded by BrainFlow except explicit user actions / cloud LLM if included in prompt |
| Indexes, embeddings | Local app data | No (rebuildable) |
| API keys, Git tokens | OS keychain | To provider/GitHub per protocol |
| Crash/telemetry | Local; upload opt-in | Only if enabled |
| Model registry cache | Local | Fetch manifests/weights with consent |

---

## 3. Logging and redaction

By default logs **must not** contain:

- File contents / note bodies  
- Raw prompts  
- Absolute paths that identify user directories (prefer vault-relative / redacted)  
- Credentials / tokens  
- Personal identifiers beyond anonymous device install id (if any)

Implementation: `brainflow_app_core::redact` ([crates/app-core/src/redact.rs](../crates/app-core/src/redact.rs)). Crash upload policy: [CRASH_REPORTING.md](CRASH_REPORTING.md).

Opt-in diagnostics may include more only after explicit consent and in-product preview where feasible.

---

## 4. LLM providers

- Local (Ollama etc.): content stays on machine subject to that runtime’s config.  
- Cloud: show **request preview** for outbound content when policy requires; enforce allowlists and spend limits.  
- Maximum Privacy policy prefers local and blocks cloud without override.  
- Providers’ own retention policies are outside BrainFlow control — disclose that.

---

## 5. GitHub sync privacy

- Private repositories: access-controlled by GitHub ACLs and org policies.  
- Collaborators and GitHub can read content.  
- Not end-to-end encrypted.  
- Optional client-side encrypted vault mode: **deferred** until ordinary merge/recovery proven (encryption harms diffs/merges).

---

## 6. Embeddings and search

- Embeddings may encode sensitive semantics; keep local; exclude from Git.  
- Rebuild after policy changes (e.g., redaction rules tightened).

---

## 7. Children / sensitive domains

No special children’s product claim in v1. Users handling regulated data (PHI, etc.) must assess fitness themselves; BrainFlow does not claim HIPAA/FedRAMP by default.

---

## 8. Retention

- Audit trail retention user-configurable.  
- Crash reports retained locally per settings; deleted on user request.  
- Uninstall should document what remains (vault is user-owned and untouched).

---

## 9. Acceptance criteria

- AC-PRV-01: Telemetry defaults off; enabling requires consent UI.  
- AC-PRV-02: Log redaction unit tests for prompt-like and path-like strings.  
- AC-PRV-03: Cloud send shows preview when Maximum Privacy overridden.  
- AC-PRV-04: Sync onboarding states non-E2E encryption plainly.  
- AC-PRV-05: Indexes excluded from Git in default vault gitignore template.
