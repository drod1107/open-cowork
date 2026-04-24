"""Model picker.

Queries the declared provider's model-list endpoint and returns a uniform
`[{"id": str, "supports_vision": bool | None}]` shape for the UI.

We cache results in memory for a short TTL; the UI "refresh" button passes
`force=True` to bypass the cache.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config_loader import load_config


@dataclass
class Model:
    id: str
    supports_vision: bool | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "supports_vision": self.supports_vision}


_VISION_HINTS = ("vision", "vl", "llava", "qwen2.5-vl", "pixtral", "minicpm-v", "bakllava")


def _guess_vision(model_id: str, raw: dict[str, Any] | None = None) -> bool | None:
    lid = model_id.lower()
    if any(h in lid for h in _VISION_HINTS):
        return True
    if raw:
        caps = raw.get("capabilities") or raw.get("details") or {}
        if isinstance(caps, dict):
            if "vision" in caps or caps.get("family", "").lower() in _VISION_HINTS:
                return True
    return None


class ProviderClient:
    def __init__(
        self,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        cache_ttl: float = 30.0,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        cfg = load_config()
        self.provider = (provider or cfg.get("provider", "ollama")).lower()
        self.base_url = (base_url or cfg.get("base_url", "http://localhost:11434")).rstrip("/")
        self._cache_ttl = cache_ttl
        self._cached: list[Model] | None = None
        self._cached_at: float = 0.0
        self._http = http

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=5.0)
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def list_models(self, *, force: bool = False) -> list[Model]:
        if not force and self._cached is not None and (time.time() - self._cached_at) < self._cache_ttl:
            return self._cached

        client = await self._client()
        if self.provider == "ollama":
            models = await self._list_ollama(client)
        elif self.provider in ("lmstudio", "vllm", "sglang"):
            models = await self._list_openai_compatible(client)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        self._cached = models
        self._cached_at = time.time()
        return models

    async def _list_ollama(self, client: httpx.AsyncClient) -> list[Model]:
        resp = await client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        payload = resp.json()
        out: list[Model] = []
        for entry in payload.get("models", []):
            name = entry.get("name") or entry.get("model")
            if not name:
                continue
            out.append(Model(id=name, supports_vision=_guess_vision(name, entry), raw=entry))
        return out

    async def _list_openai_compatible(self, client: httpx.AsyncClient) -> list[Model]:
        resp = await client.get(f"{self.base_url}/v1/models")
        resp.raise_for_status()
        payload = resp.json()
        out: list[Model] = []
        for entry in payload.get("data", []):
            mid = entry.get("id")
            if not mid:
                continue
            out.append(Model(id=mid, supports_vision=_guess_vision(mid, entry), raw=entry))
        return out
