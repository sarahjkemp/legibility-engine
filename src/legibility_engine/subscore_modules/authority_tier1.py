from __future__ import annotations

from ..collectors.search import search_web
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .authority_lists import TIER_1_DOMAINS
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    hits = []
    for domain in TIER_1_DOMAINS:
        results = await search_web(f'site:{domain} "{target.company_name}"', settings, limit=2)
        if results:
            hits.extend(results[:1])
    count = len(hits)
    score = 0.0 if count == 0 else 50.0 if count <= 2 else 80.0 if count <= 5 else 100.0
    return SubScoreResult(
        score=score,
        confidence=0.75 if hits else 0.55,
        evidence=[evidence(item["url"], item.get("title") or item.get("snippet") or "") for item in hits[:8]],
        findings=[SubScoreFinding(severity="medium" if count == 0 else "low", text=f"{count} tier-1 publication matches were surfaced via site-restricted search.")],
        raw_data={"tier_1_hits": hits, "domains_checked": TIER_1_DOMAINS},
    )
