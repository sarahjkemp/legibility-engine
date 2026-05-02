from __future__ import annotations

from ..config import EngineSettings
from .transport import get_json


async def lookup_domains(domains: list[str], settings: EngineSettings) -> dict[str, dict]:
    if not domains or not settings.openpagerank_api_key:
        return {}
    params = [(f"domains[{index}]", domain) for index, domain in enumerate(domains[:20])]
    query = "&".join(f"{key}={value}" for key, value in params)
    payload = await get_json(
        f"https://openpagerank.com/api/v1.0/getPageRank?{query}",
        settings,
        headers={"API-OPR": settings.openpagerank_api_key},
        cache_namespace="openpagerank_lookup",
    )
    response = (payload or {}).get("response") or []
    return {
        item.get("domain", ""): {
            "page_rank_decimal": item.get("page_rank_decimal"),
            "rank": item.get("rank"),
            "status_code": item.get("status_code"),
        }
        for item in response
        if item.get("domain")
    }
