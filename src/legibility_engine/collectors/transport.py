from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..cache import CacheStore, HostRateLimiter
from ..config import EngineSettings


def _cache_store(settings: EngineSettings) -> CacheStore:
    return CacheStore(Path(settings.cache_dir))


_rate_limiter = HostRateLimiter(max_requests_per_second=2.0)


async def get_text(
    url: str,
    settings: EngineSettings,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    cache_namespace: str = "http_text",
) -> str:
    cache_key = _cache_key(url, params)
    cache = _cache_store(settings)
    cached = cache.get(cache_namespace, cache_key)
    if cached is not None:
        return str(cached)
    text = await _fetch_text(url, settings, params=params, headers=headers)
    cache.set(cache_namespace, cache_key, text)
    return text


async def get_json(
    url: str,
    settings: EngineSettings,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    cache_namespace: str = "http_json",
) -> Any:
    cache_key = _cache_key(url, params)
    cache = _cache_store(settings)
    cached = cache.get(cache_namespace, cache_key)
    if cached is not None:
        return cached
    payload = await _fetch_json(url, settings, params=params, headers=headers)
    cache.set(cache_namespace, cache_key, payload)
    return payload


async def _fetch_text(
    url: str,
    settings: EngineSettings,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    merged_headers = {"User-Agent": settings.user_agent, **(headers or {})}
    await _rate_limiter.wait(urlparse(url).netloc)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=settings.timeout_seconds,
        headers=merged_headers,
    ) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
    return response.text


async def _fetch_json(
    url: str,
    settings: EngineSettings,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    merged_headers = {"User-Agent": settings.user_agent, **(headers or {})}
    await _rate_limiter.wait(urlparse(url).netloc)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=settings.timeout_seconds,
        headers=merged_headers,
    ) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
    return response.json()


def _cache_key(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    parts = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return f"{url}?{parts}"
