## Summary

<!-- What and why. Link issues if applicable. -->

## Test plan

- [ ] `npm run smoke:vertical-slice` (or note why N/A)
- [ ] `npm run typecheck -w desktop` and/or `cargo test …` / `pytest` for touched areas
- [ ] `npm run test:schemas` if schemas changed
- [ ] Manual check in `tauri dev` if UI/shell changed
- [ ] Live Ollama path exercised if LLM behavior changed (or fail-closed path verified)

## Docs

- [ ] Updated `docs/` / README / ROADMAP notes if contracts or status changed
- [ ] Did **not** edit `.cursor/plans/`
- [ ] Claims match [docs/REMAINING_GAPS.md](../docs/REMAINING_GAPS.md) (no fake signing/CI/GA)

## Breaking changes

- [ ] None
- [ ] Yes — describe migration / compatibility impact:
