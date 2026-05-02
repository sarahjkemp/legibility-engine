from __future__ import annotations

from ..config import EngineSettings
from ..models import AuditTarget
from .site import fetch_internal_pages
from .transport import get_text


def declared_owned_channels(target: AuditTarget) -> list[dict]:
    channels = [
        {"role": "company", "platform": "website", "url": str(target.primary_url)},
        {"role": "company", "platform": "linkedin", "url": _first_value(target.company_linkedin_url)},
        {"role": "company", "platform": "substack", "url": _first_value(target.company_substack_url, target.official_substack_url)},
        {"role": "company", "platform": "medium", "url": _first_value(target.company_medium_url, target.official_medium_url)},
        {"role": "company", "platform": "youtube", "url": _first_value(target.company_youtube_url, target.official_youtube_url)},
        {"role": "spokesperson", "platform": "linkedin", "url": _first_value(target.spokesperson_linkedin_url, target.founder_linkedin_url)},
        {"role": "spokesperson", "platform": "substack", "url": _first_value(target.spokesperson_substack_url)},
        {"role": "spokesperson", "platform": "medium", "url": _first_value(target.spokesperson_medium_url)},
        {"role": "spokesperson", "platform": "youtube", "url": _first_value(target.spokesperson_youtube_url)},
    ]
    return [channel for channel in channels if channel["url"]]


async def fetch_owned_channel_surfaces(target: AuditTarget, settings: EngineSettings) -> list[dict]:
    surfaces: list[dict] = []
    for channel in declared_owned_channels(target):
        if channel["platform"] == "website":
            pages = await fetch_internal_pages(channel["url"], settings, limit=6)
            for page in pages[:6]:
                surfaces.append(
                    {
                        "role": channel["role"],
                        "platform": "website",
                        "url": page["url"],
                        "text": page.get("text", "")[:4000],
                        "title": page.get("metadata", {}).get("title") or "",
                        "source": "declared_input",
                    }
                )
            continue
        try:
            text = await get_text(channel["url"], settings, cache_namespace=f"{channel['platform']}_owned_channels")
        except Exception:
            continue
        surfaces.append(
            {
                "role": channel["role"],
                "platform": channel["platform"],
                "url": channel["url"],
                "text": text[:4000],
                "title": "",
                "source": "declared_input",
            }
        )
    return surfaces


def _first_value(*values: object) -> str | None:
    for value in values:
        if value:
            return str(value)
    return None
