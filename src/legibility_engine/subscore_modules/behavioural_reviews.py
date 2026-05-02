from __future__ import annotations

import re

from ..collectors.search import search_web
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    queries = [
        f'"{target.company_name}" Trustpilot',
        f'"{target.company_name}" "Google reviews"',
        f'"{target.company_name}" G2',
        f'"{target.company_name}" Capterra',
        f'"{target.company_name}" Glassdoor',
    ]
    hits = []
    for query in queries:
        hits.extend(await search_web(query, settings, limit=2))
    if not hits:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No public review-platform surfaces were found in the sampled search results.")],
            raw_data={"hits": []},
        )
    volume = min(50, len(hits) * 8)
    ratings = []
    for item in hits:
        combined = " ".join([item.get("title", ""), item.get("snippet", "")])
        match = re.search(r"([1-5](?:\.\d)?)\s*/\s*5", combined)
        if match:
            ratings.append(float(match.group(1)))
    avg = sum(ratings) / len(ratings) if ratings else 4.0
    sentiment = min(50, max(0, (avg / 5) * 50))
    score = round(min(100, volume + sentiment), 2)
    return SubScoreResult(
        score=score,
        confidence=0.6,
        evidence=[evidence(item["url"], item.get("title") or item.get("snippet") or "") for item in hits[:8]],
        findings=[SubScoreFinding(severity="medium" if len(hits) < 2 else "low", text=f"{len(hits)} public review-surface matches were found with an inferred average rating of {avg:.1f}/5.")],
        raw_data={"hits": hits, "ratings": ratings, "average_rating": avg},
    )
