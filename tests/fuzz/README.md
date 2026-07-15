# Fuzz entrypoints

Harness stubs for importer, Markdown, workflow JSON, Git conflict, and IPC fuzzing.
Replace `todo!` / skip bodies with `cargo fuzz` / `atheris` targets as parsers land.

## Layout

| Path | Target |
|------|--------|
| `tests/fuzz/workflow_ir/` | Workflow IR JSON schema survivors |
| `tests/fuzz/markdown/` | Markdown / sanitizer inputs |
| `tests/fuzz/ipc/` | Worker JSON-RPC line framing |
| `tests/fuzz/archives/` | Archive bombs / decompression limits (ingestion) |

## Running (CI stub)

```bash
node scripts/fuzz-entrypoint.cjs
```

Nightly CI should eventually call real fuzz binaries with time budgets ([QA_STRATEGY.md](../docs/QA_STRATEGY.md)).
