from __future__ import annotations

from ..collectors.search import (
    count_distinct_domains,
    dedupe_by_registered_domain,
    filter_search_results,
    search_web,
    verify_entity_matches,
)
from ..config import AuditConfig, EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, root_domain


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    query = f'"{target.company_name}" -site:{root_domain(str(target.primary_url))}'
    profile = build_entity_profile(target)
    results = await search_web(query, settings, limit=12)
    filtered = filter_search_results(
        results,
        owned_domain=root_domain(str(target.primary_url)),
        excluded_domains=set(config.owned_surface_domains),
        sector=target.sector,
    )
    verified = await verify_entity_matches(filtered, profile, settings)
    deduped = dedupe_by_registered_domain(verified)
    domains = count_distinct_domains(deduped, excluded_domains=set(config.owned_surface_domains))
    count = len(domains)
    if count == 0:
        score = 0.0
    elif count <= 2:
        score = 25.0
    elif count <= 5:
        score = 50.0
    elif count <= 10:
        score = 75.0
    else:
        score = 100.0
    findings = [
        SubScoreFinding(
            severity="medium" if count < 3 else "low",
            text=f"External search surfaced {count} verified third-party entity matches after filtering, verification, and registered-domain deduplication.",
        )
    ]
    return SubScoreResult(
        score=score,
        confidence=0.8 if deduped else 0.55,
        evidence=[evidence(item["url"], f'{item["title"]} — {item.get("snippet", "")}') for item in deduped[:8]],
        findings=findings,
        raw_data={"query": query, "results": deduped, "raw_candidates": filtered, "distinct_domains": domains, "entity_profile": profile.__dict__},
    )
