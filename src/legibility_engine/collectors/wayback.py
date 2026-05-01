from __future__ import annotations

from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import EngineSettings


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type(httpx.HTTPError),
)
async def fetch_snapshots(url: str, settings: EngineSettings, limit: int = 3) -> list[dict]:
    api_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={quote(url, safe='')}&output=json&fl=timestamp,original,statuscode&filter=statuscode:200&limit={limit}"
    )
    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(timeout=settings.timeout_seconds, headers=headers) as client:
        response = await client.get(api_url)
        response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or len(data) <= 1:
        return []
    rows = data[1:]
    return [
        {
            "timestamp": row[0],
            "original": row[1],
            "status_code": row[2],
            "archive_url": f"https://web.archive.org/web/{row[0]}/{row[1]}",
        }
        for row in rows
        if len(row) >= 3
    ]
