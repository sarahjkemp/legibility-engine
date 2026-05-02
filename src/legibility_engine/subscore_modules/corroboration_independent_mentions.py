from __future__ import annotations

from ..collectors.search import count_distinct_domains, filter_search_results, search_web
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, root_domain


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    query = f'"{target.company_name}" -site:{root_domain(str(target.primary_url))}'
    results = await search_web(query, settings, limit=12)
    filtered = filter_search_results(
        results,
        owned_domain=root_domain(str(target.primary_url)),
        excluded_domains=set(config.owned_surface_domains),
        sector=target.sector,
    )
    domains = count_distinct_domains(filtered, excluded_domains=set(config.owned_surface_domains))
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
            text=f"External search surfaced {count} distinct third-party domains after filtering owned and social surfaces.",
        )
    ]
    return SubScoreResult(
        score=score,
        confidence=0.75 if filtered else 0.55,
        evidence=[evidence(item["url"], f'{item["title"]} — {item.get("snippet", "")}') for item in filtered[:8]],
        findings=findings,
        raw_data={"query": query, "results": filtered, "distinct_domains": domains},
    )
