from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import EngineSettings
from .transport import get_json


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type(httpx.HTTPError),
)
async def fetch_snapshots(url: str, settings: EngineSettings) -> list[dict]:
    windows = [6, 12, 24]
    snapshots = []
    for months in windows:
        target_date = datetime.now(timezone.utc) - timedelta(days=months * 30)
        payload = await get_json(
            "https://archive.org/wayback/available",
            settings,
            params={"url": url, "timestamp": target_date.strftime("%Y%m%d")},
            cache_namespace="wayback_available",
        )
        archived = (((payload or {}).get("archived_snapshots") or {}).get("closest")) or {}
        if not archived:
            continue
        snapshots.append(
            {
                "window_months": months,
                "timestamp": archived.get("timestamp"),
                "original": archived.get("url") or url,
                "status_code": archived.get("status"),
                "archive_url": archived.get("url")
                or f"https://web.archive.org/web/{quote(url, safe='')}",
            }
        )
    return snapshots
