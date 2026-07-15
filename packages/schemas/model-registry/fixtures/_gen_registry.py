"""One-shot: write signed registry.v1.json fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "services" / "ai-worker"))

from brainflow_worker.gateway.registry import content_digest, sign_manifest_hmac  # noqa: E402

models = [
    {
        "id": "llama3.2:3b",
        "display_name": "Llama 3.2 3B",
        "source": "ollama",
        "runtime_name": "llama3.2:3b",
        "preferred_provider": "ollama",
        "release_date": "2024-09-25",
        "digests": ["sha256:llama32-3b-demo"],
        "quantizations": ["Q4_K_M"],
        "parameter_count": 3.2e9,
        "context_lengths": [8192, 128000],
        "modalities": ["text"],
        "capabilities": {"tools": True, "json_schema": True, "embeddings": False},
        "license": "Llama 3.2 Community",
        "known_security_issues": [],
        "memory_formula": {
            "id": "bf-mem-v1",
            "params": {"weights_mb": 2200, "kv_mb_per_1k_ctx": 6, "runtime_overhead_mb": 400},
        },
        "quality_scores": [
            {
                "metric": "brainflow_workflow_actionability",
                "metric_version": "0.1",
                "value": 0.72,
                "dataset_id": "bf-domain-study-v0",
                "job_id": "eval-2026-07-01-a",
                "timestamp": "2026-07-01T12:00:00Z",
                "model_digest": "sha256:llama32-3b-demo",
                "hardware_class": "mid-windows",
            }
        ],
        "benchmark_refs": ["tests/evals/model_selection"],
        "download_size_mb": 2000,
        "eval_reliability": 0.75,
        "performance_floor": 0.8,
        "quant_penalty": 0.05,
        "remote_code_required": False,
    },
    {
        "id": "qwen2.5:7b",
        "display_name": "Qwen2.5 7B",
        "source": "ollama",
        "runtime_name": "qwen2.5:7b",
        "preferred_provider": "ollama",
        "release_date": "2024-09-19",
        "digests": ["sha256:qwen25-7b-demo"],
        "quantizations": ["Q4_K_M"],
        "parameter_count": 7.6e9,
        "context_lengths": [32768],
        "modalities": ["text"],
        "capabilities": {"tools": True, "json_schema": True, "embeddings": False},
        "license": "Apache-2.0",
        "known_security_issues": [],
        "memory_formula": {
            "id": "bf-mem-v1",
            "params": {"weights_mb": 4800, "kv_mb_per_1k_ctx": 10, "runtime_overhead_mb": 512},
        },
        "quality_scores": [
            {
                "metric": "brainflow_workflow_actionability",
                "metric_version": "0.1",
                "value": 0.84,
                "dataset_id": "bf-domain-study-v0",
                "job_id": "eval-2026-07-01-b",
                "timestamp": "2026-07-01T12:00:00Z",
                "model_digest": "sha256:qwen25-7b-demo",
                "hardware_class": "mid-windows",
            }
        ],
        "benchmark_refs": ["tests/evals/model_selection"],
        "download_size_mb": 4600,
        "eval_reliability": 0.82,
        "performance_floor": 0.65,
        "quant_penalty": 0.05,
        "remote_code_required": False,
    },
    {
        "id": "llava:7b",
        "display_name": "LLaVA 7B",
        "source": "ollama",
        "runtime_name": "llava:7b",
        "preferred_provider": "ollama",
        "release_date": "2024-01-01",
        "digests": ["sha256:llava-7b-demo"],
        "quantizations": ["Q4_0"],
        "parameter_count": 7e9,
        "context_lengths": [4096],
        "modalities": ["text", "vision"],
        "capabilities": {"tools": False, "json_schema": True, "embeddings": False},
        "license": "Apache-2.0",
        "known_security_issues": [],
        "memory_formula": {
            "id": "bf-mem-v1",
            "params": {"weights_mb": 4500, "kv_mb_per_1k_ctx": 8, "runtime_overhead_mb": 600},
        },
        "quality_scores": [
            {
                "metric": "brainflow_vision_extract",
                "metric_version": "0.1",
                "value": 0.7,
                "dataset_id": "bf-vision-v0",
                "job_id": "eval-2026-07-01-c",
                "timestamp": "2026-07-01T12:00:00Z",
                "model_digest": "sha256:llava-7b-demo",
                "hardware_class": "mid-windows",
            }
        ],
        "benchmark_refs": ["tests/evals/model_selection"],
        "download_size_mb": 4500,
        "eval_reliability": 0.7,
        "performance_floor": 0.55,
        "quant_penalty": 0.08,
        "remote_code_required": False,
    },
    {
        "id": "nomic-embed-text",
        "display_name": "Nomic Embed Text",
        "source": "ollama",
        "runtime_name": "nomic-embed-text",
        "preferred_provider": "ollama",
        "release_date": "2024-02-01",
        "digests": ["sha256:nomic-embed-demo"],
        "quantizations": ["F16"],
        "parameter_count": 1.37e8,
        "context_lengths": [8192],
        "modalities": ["text"],
        "capabilities": {"tools": False, "json_schema": False, "embeddings": True},
        "license": "Apache-2.0",
        "known_security_issues": [],
        "memory_formula": {
            "id": "bf-mem-v1",
            "params": {"weights_mb": 274, "kv_mb_per_1k_ctx": 1, "runtime_overhead_mb": 128},
        },
        "quality_scores": [
            {
                "metric": "brainflow_retrieval_ndcg",
                "metric_version": "0.1",
                "value": 0.78,
                "dataset_id": "bf-retrieve-v0",
                "job_id": "eval-2026-07-01-d",
                "timestamp": "2026-07-01T12:00:00Z",
                "model_digest": "sha256:nomic-embed-demo",
                "hardware_class": "mid-windows",
            }
        ],
        "benchmark_refs": ["tests/evals/model_selection"],
        "download_size_mb": 274,
        "eval_reliability": 0.8,
        "performance_floor": 0.9,
        "quant_penalty": 0.0,
        "remote_code_required": False,
    },
    {
        "id": "huge-70b-remote",
        "display_name": "Demo 70B (fit fail)",
        "source": "ollama",
        "runtime_name": "llama3.1:70b",
        "preferred_provider": "ollama",
        "release_date": "2024-07-01",
        "digests": ["sha256:llama70-demo"],
        "quantizations": ["Q4_K_M"],
        "parameter_count": 70e9,
        "context_lengths": [128000],
        "modalities": ["text"],
        "capabilities": {"tools": True, "json_schema": True, "embeddings": False},
        "license": "Llama 3.1 Community",
        "known_security_issues": [],
        "memory_formula": {
            "id": "bf-mem-v1",
            "params": {"weights_mb": 40000, "kv_mb_per_1k_ctx": 40, "runtime_overhead_mb": 2048},
        },
        "quality_scores": [
            {
                "metric": "brainflow_workflow_actionability",
                "metric_version": "0.1",
                "value": 0.95,
                "dataset_id": "bf-domain-study-v0",
                "job_id": "eval-2026-07-01-e",
                "timestamp": "2026-07-01T12:00:00Z",
                "model_digest": "sha256:llama70-demo",
                "hardware_class": "high-windows",
            }
        ],
        "benchmark_refs": ["tests/evals/model_selection"],
        "download_size_mb": 40000,
        "eval_reliability": 0.9,
        "performance_floor": 0.3,
        "quant_penalty": 0.1,
        "remote_code_required": False,
    },
    {
        "id": "unsafe-remote-code",
        "display_name": "Unsafe Remote Code Demo",
        "source": "huggingface",
        "runtime_name": "unsafe-remote",
        "preferred_provider": "custom",
        "release_date": "2024-01-01",
        "digests": ["sha256:unsafe-demo"],
        "quantizations": ["fp16"],
        "parameter_count": 1e9,
        "context_lengths": [4096],
        "modalities": ["text"],
        "capabilities": {"tools": True, "json_schema": True},
        "license": "unknown-proprietary",
        "known_security_issues": ["remote_code_required"],
        "memory_formula": {"id": "bf-mem-v1", "params": {"weights_mb": 2000}},
        "quality_scores": [],
        "benchmark_refs": [],
        "download_size_mb": 2000,
        "remote_code_required": True,
    },
]

manifest = {
    "manifest_version": 1,
    "issued_at": "2026-07-15T00:00:00Z",
    "issuer": "brainflow-dev",
    "previous_manifest_digest": None,
    "rollout_stage": "ga",
    "models": models,
}
signed = sign_manifest_hmac(manifest, key_id="brainflow-dev", secret=b"brainflow-dev-hmac-key")
out = ROOT / "packages" / "schemas" / "model-registry" / "fixtures" / "registry.v1.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
print(content_digest(signed))
print(out)
