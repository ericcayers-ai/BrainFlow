"""Mockable HTTP capability tests for Anthropic / Gemini / OpenRouter / custom."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from brainflow_worker.gateway.budget import BudgetExceeded, RequestBudget
from brainflow_worker.gateway.pins import PinViolation, assert_pins_stable, resolve_for_run
from brainflow_worker.gateway.probes import run_capability_probes
from brainflow_worker.gateway.providers.anthropic import AnthropicAdapter
from brainflow_worker.gateway.providers.gemini import GeminiAdapter
from brainflow_worker.gateway.providers.openrouter import CustomOpenAICompatAdapter, OpenRouterAdapter
from brainflow_worker.gateway.secrets import set_secret


def _json_response(request: httpx.Request, status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, request=request)


@pytest.fixture()
def secret_memory(monkeypatch):
    monkeypatch.delenv("BRAINFLOW_SECRET_ANTHROPIC", raising=False)
    monkeypatch.delenv("BRAINFLOW_SECRET_GEMINI", raising=False)
    monkeypatch.delenv("BRAINFLOW_SECRET_OPENROUTER", raising=False)
    set_secret("anthropic", "test-anthropic-key", prefer_keyring=False)
    set_secret("gemini", "test-gemini-key", prefer_keyring=False)
    set_secret("openrouter", "test-openrouter-key", prefer_keyring=False)


def test_anthropic_health_and_chat_mock(secret_memory):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/models"):
            return _json_response(
                request,
                200,
                {"data": [{"id": "claude-3-5-haiku-latest"}]},
            )
        if request.url.path.endswith("/v1/messages"):
            payload = json.loads(request.content.decode())
            assert payload["max_tokens"] <= 64
            return _json_response(
                request,
                200,
                {
                    "content": [{"type": "text", "text": '{"ok":true,"probe":"json"}'}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            )
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    budget = RequestBudget(max_tokens=64, label="anthropic-test")
    adapter = AnthropicAdapter(transport=transport, default_budget=budget)
    health = adapter.health()
    assert health["ok"] is True
    assert "claude-3-5-haiku-latest" in health["models"]

    raw = adapter.chat(
        model="claude-3-5-haiku-latest",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=128,
    )
    assert raw["content"][0]["text"].startswith("{")
    assert budget.tokens_used == 15

    probes = run_capability_probes(adapter, model="claude-3-5-haiku-latest", which=["json_schema"])
    assert probes["probes"]["json_schema"]["ok"] is True


def test_gemini_health_and_chat_mock(secret_memory):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models") and request.method == "GET":
            return _json_response(
                request,
                200,
                {
                    "models": [
                        {
                            "name": "models/gemini-1.5-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                },
            )
        if ":generateContent" in request.url.path:
            return _json_response(
                request,
                200,
                {
                    "candidates": [
                        {"content": {"parts": [{"text": '{"ok":true,"probe":"json"}'}]}}
                    ],
                    "usageMetadata": {"totalTokenCount": 22},
                },
            )
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    budget = RequestBudget(max_tokens=100, label="gemini-test")
    adapter = GeminiAdapter(transport=transport, default_budget=budget)
    assert adapter.health()["ok"] is True
    raw = adapter.chat(
        model="gemini-1.5-flash",
        messages=[{"role": "user", "content": "ping"}],
        format="json",
    )
    text = raw["candidates"][0]["content"]["parts"][0]["text"]
    assert "ok" in text
    assert budget.tokens_used == 22


def test_openrouter_and_custom_mock(secret_memory):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return _json_response(request, 200, {"data": [{"id": "test/model"}]})
        if request.url.path.endswith("/chat/completions"):
            body = json.loads(request.content.decode())
            assert "max_tokens" in body
            return _json_response(
                request,
                200,
                {
                    "choices": [{"message": {"content": '{"ok":true}'}}],
                    "usage": {"total_tokens": 9},
                },
            )
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    budget = RequestBudget(max_tokens=32, label="or")
    or_adapter = OpenRouterAdapter(transport=transport, default_budget=budget)
    assert or_adapter.health()["ok"] is True
    or_adapter.chat(model="test/model", messages=[{"role": "user", "content": "hi"}], max_tokens=16)

    custom = CustomOpenAICompatAdapter(
        base_url="http://127.0.0.1:9/v1",
        transport=transport,
        require_tls=False,
        default_budget=RequestBudget(max_tokens=8, label="custom"),
    )
    assert custom.health()["ok"] is True


def test_budget_blocks_overspend(secret_memory):
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            200,
            {
                "content": [{"type": "text", "text": "x"}],
                "usage": {"input_tokens": 50, "output_tokens": 50},
            },
        )

    budget = RequestBudget(max_tokens=40, label="tight")
    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler), default_budget=budget)
    with pytest.raises(BudgetExceeded):
        # planned clamp would allow 40, but usage 100 exceeds after record
        adapter.chat(model="claude", messages=[{"role": "user", "content": "x"}], max_tokens=40)


def test_pins_assert_stable_blocks_mid_run_swap():
    pinned = {"planner": {"provider": "ollama", "name": "a", "digest": "sha256:1"}}
    requested = {"planner": {"provider": "ollama", "name": "b", "digest": "sha256:2"}}
    with pytest.raises(PinViolation):
        assert_pins_stable(pinned=pinned, requested=requested, run_active=True)
    res = resolve_for_run(
        policy="auto",
        pinned=pinned,
        recommended=requested,
        run_active=True,
    )
    assert res["changed"] is False
    assert res["pins"]["planner"]["digest"] == "sha256:1"


def test_anthropic_without_key_fail_closed(monkeypatch):
    from brainflow_worker.gateway import secrets as secrets_mod

    monkeypatch.setattr(secrets_mod, "_MEMORY", {})
    monkeypatch.delenv("BRAINFLOW_SECRET_ANTHROPIC", raising=False)
    adapter = AnthropicAdapter()
    h = adapter.health()
    assert h["ok"] is False
    assert "missing" in (h.get("error") or "").lower()
