"""Shared HTTP helpers for provider adapters (injectable transport for tests)."""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

import httpx

ClientFactory = Callable[..., httpx.Client]


def is_loopback(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def default_client(**kwargs: Any) -> httpx.Client:
    return httpx.Client(**kwargs)


def make_client(
    *,
    base_url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    transport: httpx.BaseTransport | None = None,
    client_factory: ClientFactory | None = None,
) -> httpx.Client:
    factory = client_factory or default_client
    kwargs: dict[str, Any] = {
        "base_url": base_url.rstrip("/"),
        "timeout": timeout,
        "headers": headers or {},
    }
    if transport is not None:
        kwargs["transport"] = transport
    return factory(**kwargs)
