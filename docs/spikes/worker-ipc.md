# Spike: Worker IPC

**ADR:** [0002-sidecar-transport.md](../adr/0002-sidecar-transport.md)

## Design

```text
Rust core  --spawn-->  python -m brainflow_worker
           <--- stdin/stdout JSON-RPC lines --->
```

- One JSON object per line (JSON-RPC 2.0).
- Methods: `ping`, `llm.health`, `workflow.generate`, `schema.root`.
- Dev-only `--http-loopback`: `127.0.0.1` + ephemeral port + `Authorization: Bearer <token>`.

## Anti-patterns rejected

- Fixed port `localhost:7xxx` without auth.
- Worker as a long-lived public HTTP service.

## Foundation slice note

Jobs currently spawn a short-lived worker process per RPC. Next step: supervised long-lived child with reconnect and job queues in `crates/app-core`.
