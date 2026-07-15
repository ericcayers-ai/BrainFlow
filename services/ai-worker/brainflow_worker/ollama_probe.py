from __future__ import annotations

import json
from typing import Any

from brainflow_worker.gateway.providers.ollama import OllamaAdapter, ollama_base_url

# Back-compat export for workflow_gen and spikes
OLLAMA_BASE = ollama_base_url()


def probe_ollama(timeout_s: float = 3.0) -> dict[str, Any]:
    """Fail-closed health probe for local Ollama (delegates to gateway adapter)."""
    return OllamaAdapter().health(timeout_s=timeout_s)


def main() -> None:
    print(json.dumps(probe_ollama(), indent=2))


if __name__ == "__main__":
    main()
