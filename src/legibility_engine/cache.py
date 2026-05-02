from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


@dataclass
class CacheItem:
    namespace: str
    key: str
    value: Any
    stored_at: datetime


class CacheStore:
    def __init__(self, base_dir: Path, ttl_seconds: int = 7 * 24 * 60 * 60) -> None:
        self.base_dir = base_dir
        self.ttl = timedelta(seconds=ttl_seconds)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha256(f"{namespace}:{key}".encode("utf-8")).hexdigest()
        return self.base_dir / namespace / f"{digest}.json"

    def get(self, namespace: str, key: str) -> Any | None:
        path = self._path_for(namespace, key)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        stored_at = datetime.fromisoformat(payload["stored_at"])
        if utcnow() - stored_at > self.ttl:
            return None
        return payload.get("value")

    def set(self, namespace: str, key: str, value: Any) -> None:
        path = self._path_for(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"stored_at": utcnow().isoformat(), "value": value}
        path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")

    async def get_or_set(self, namespace: str, key: str, factory: Any) -> Any:
        cached = self.get(namespace, key)
        if cached is not None:
            return cached
        value = await factory()
        self.set(namespace, key, value)
        return value


class HostRateLimiter:
    def __init__(self, max_requests_per_second: float = 2.0) -> None:
        self.interval = 1.0 / max_requests_per_second
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_call: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = asyncio.get_running_loop().time()
            elapsed = now - self._last_call.get(host, 0.0)
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last_call[host] = asyncio.get_running_loop().time()
