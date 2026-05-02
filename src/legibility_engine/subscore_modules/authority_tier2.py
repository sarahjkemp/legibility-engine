from __future__ import annotations

from ..collectors.search import search_web
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .authority_lists import TIER_2_BY_SECTOR
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    domains = TIER_2_BY_SECTOR.get(target.sector, TIER_2_BY_SECTOR["other"])
    hits = []
    for domain in domains:
        results = await search_web(f'site:{domain} "{target.company_name}"', settings, limit=2)
        if results:
            hits.extend(results[:1])
    count = len(hits)
    score = 0.0 if count == 0 else 50.0 if count <= 2 else 80.0 if count <= 5 else 100.0
    return SubScoreResult(
        score=score,
        confidence=0.75 if hits else 0.55,
        evidence=[evidence(item["url"], item.get("title") or item.get("snippet") or "") for item in hits[:8]],
        findings=[SubScoreFinding(severity="medium" if count == 0 else "low", text=f"{count} tier-2 publication matches were surfaced for the {target.sector} sector list.")],
        raw_data={"tier_2_hits": hits, "domains_checked": domains},
    )
