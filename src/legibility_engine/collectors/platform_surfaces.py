from __future__ import annotations

from ..config import EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget
from .search import dedupe_by_registered_domain, search_web, verify_entity_matches

PLATFORM_QUERIES = {
    "substack": "site:substack.com",
    "medium": "site:medium.com",
    "youtube": "site:youtube.com",
}


async def discover_platform_surfaces(target: AuditTarget, settings: EngineSettings) -> dict[str, list[dict]]:
    profile = build_entity_profile(target)
    found: dict[str, list[dict]] = {}
    founder = target.founder_name or ""
    for platform, site_query in PLATFORM_QUERIES.items():
        queries = [f'{site_query} "{target.company_name}"']
        if founder:
            queries.append(f'{site_query} "{founder}" "{target.company_name}"')
        candidates: list[dict] = []
        for query in queries:
            candidates.extend(await search_web(query, settings, limit=4))
        verified = await verify_entity_matches(candidates, profile, settings)
        deduped = dedupe_by_registered_domain(verified)
        if deduped:
            found[platform] = deduped
    return found
