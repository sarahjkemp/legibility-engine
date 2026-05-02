from __future__ import annotations

from ..collectors.search import (
    dedupe_by_registered_domain,
    filter_to_registered_domain_allowlist,
    search_web,
    verify_entity_matches,
)
from ..config import AuditConfig, EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    domains = config.sector_tier_2_domains.get(target.sector) or config.sector_tier_2_domains.get("other") or config.tier_2_domains
    if not domains:
        raise ValueError("tier_2 domain config is missing from config/tier_lists.yaml")
    profile = build_entity_profile(target)
    hits = []
    for domain in domains:
        results = await search_web(f'site:{domain} "{target.company_name}"', settings, limit=2)
        if results:
            hits.extend(results)
    allowed = filter_to_registered_domain_allowlist(hits, set(domains))
    verified = await verify_entity_matches(allowed, profile, settings)
    deduped = dedupe_by_registered_domain(verified)
    count = len(deduped)
    score = 0.0 if count == 0 else 50.0 if count <= 2 else 80.0 if count <= 5 else 100.0
    return SubScoreResult(
        score=score,
        confidence=0.75 if deduped else 0.55,
        evidence=[evidence(item["url"], item.get("title") or item.get("snippet") or "") for item in deduped[:8]],
        findings=[SubScoreFinding(severity="medium" if count == 0 else "low", text=f"{count} tier-2 publication matches were surfaced for the {target.sector} sector list.")],
        raw_data={"tier_2_hits": deduped, "domains_checked": domains, "raw_search_hits": hits},
    )
