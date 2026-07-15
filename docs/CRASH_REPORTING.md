# Crash reporting (opt-in)

Crash and diagnostic reporting is **off by default**. Enabling it is an explicit privacy decision ([PRIVACY.md](PRIVACY.md)).

---

## 1. Product behavior

| Setting | Default | Effect |
|---------|---------|--------|
| Crash reporting | Off | Local stack traces only in app data; never uploaded |
| Extended diagnostics | Off | May include redacted breadcrumbs after separate consent |
| Analytics / product telemetry | Off / deferred | Not required for beta |

Consent UI must:

1. State what is collected (binary version, OS, crash stack, locale).  
2. State what is never collected by default (note bodies, prompts, absolute home paths, tokens).  
3. Link to this doc and [PRIVACY.md](PRIVACY.md).  
4. Allow disable-and-delete of locally queued reports.

---

## 2. Local storage

Under OS app data (not vault):

```text
BrainFlow/diagnostics/
  crashes/          # local minidumps / JSON events
  queue/            # pending uploads if opted in
```

Portable vault must never store crash payloads.

---

## 3. Redaction before any upload

Apply [log redaction](../crates/app-core) patterns (`brainflow_app_core::redact`):

- Strip bearer tokens, API keys, GitHub PATs  
- Redact absolute user profile paths → `<HOME>` / vault-relative  
- Drop prompt bodies and file contents  
- Hash device identifiers if an install id is present  

Unit tests: `crates/app-core` redaction module.

---

## 4. Acceptance criteria

- AC-CRASH-01: Fresh install has reporting disabled.  
- AC-CRASH-02: Upload path unreachable unless consent flag set.  
- AC-CRASH-03: Redaction tests cover path-like and secret-like strings.  
- AC-CRASH-04: User can delete local crash directory from settings.
