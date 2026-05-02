from __future__ import annotations

from urllib.parse import urlparse

from ..config import EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget
from ..matching import get_registered_domain
from .site import fetch_internal_pages
from .search import dedupe_by_registered_domain, search_web, verify_entity_matches

PLATFORM_QUERIES = {
    "substack": "site:substack.com",
    "medium": "site:medium.com",
    "youtube": "site:youtube.com",
}

PLATFORM_DOMAINS = {
    "substack": {"substack.com"},
    "medium": {"medium.com"},
    "youtube": {"youtube.com", "youtu.be"},
}

PLATFORM_INPUT_FIELDS = {
    "substack": "official_substack_url",
    "medium": "official_medium_url",
    "youtube": "official_youtube_url",
}


async def discover_platform_surfaces(target: AuditTarget, settings: EngineSettings) -> dict[str, list[dict]]:
    profile = build_entity_profile(target)
    found: dict[str, list[dict]] = {}
    founder = target.founder_name or ""
    for platform, site_query in PLATFORM_QUERIES.items():
        explicit = _explicit_platform_items(target, platform)
        site_links = await _discover_owned_site_links(target, settings, platform)
        direct_items = dedupe_by_registered_domain(explicit + site_links)

        if direct_items:
            found[platform] = direct_items
            continue

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


def _explicit_platform_items(target: AuditTarget, platform: str) -> list[dict]:
    field_name = PLATFORM_INPUT_FIELDS[platform]
    url = getattr(target, field_name, None)
    if not url:
        return []
    url_string = str(url)
    return [
        {
            "url": url_string,
            "title": f"Official {platform.title()} surface for {target.company_name}",
            "snippet": f"Declared official {platform.title()} URL on the audit target.",
            "domain": urlparse(url_string).netloc,
            "registered_domain": get_registered_domain(url_string),
            "source": "explicit_input",
        }
    ]


async def _discover_owned_site_links(target: AuditTarget, settings: EngineSettings, platform: str) -> list[dict]:
    links: list[dict] = []
    try:
        pages = await fetch_internal_pages(str(target.primary_url), settings, limit=6)
    except Exception:
        return links
    allowed_domains = PLATFORM_DOMAINS[platform]
    seen_urls: set[str] = set()
    for page in pages:
        for link in page.get("links", []):
            registered_domain = get_registered_domain(link)
            if registered_domain not in allowed_domains:
                continue
            if link in seen_urls:
                continue
            seen_urls.add(link)
            links.append(
                {
                    "url": link,
                    "title": f"Owned-site linked {platform.title()} surface",
                    "snippet": f"Linked from {page.get('url', target.primary_url)}",
                    "domain": urlparse(link).netloc,
                    "registered_domain": registered_domain,
                    "source": "owned_site_link",
                }
            )
    return links
