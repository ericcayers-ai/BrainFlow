# Ingestion corpus

Licensing-safe fixtures for DocumentBundle golden / adversarial tests.

| Path | Purpose |
|------|---------|
| `golden/` | Happy-path samples per core adapter family |
| `adversarial/` | Malformed HTML/JSON/notebook/ODT and injection-style content |
| `expected/` | Reserved for snapshot expectations |

Golden fixtures (current): `sample.md`, `.txt`, `.html`, `.json`, `.yaml`, `.csv`, `.py`, `.pdf`, `.png`, `.ipynb`, `.odt`, `.wav`.

Adversarial: `broken.json`, `broken.ipynb`, `inject.html`, `inject.ipynb`, `truncated.odt`.

Python tests: `services/ai-worker/tests/test_intake.py`.  
Regenerate generated fixtures: `python services/ai-worker/scripts/gen_corpus_fixtures.py`.  
Zip-bomb and exec-in-archive cases are generated in-test (not stored as large binaries).
