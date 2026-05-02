from __future__ import annotations

import re

from ..collectors.search import dedupe_by_registered_domain, search_web, verify_entity_matches
from ..config import AuditConfig, EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    profile = build_entity_profile(target)
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
    verified = dedupe_by_registered_domain(await verify_entity_matches(hits, profile, settings))
    if not verified:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No public review-platform surfaces were found in the sampled search results.")],
            raw_data={"hits": [], "raw_candidates": hits, "entity_profile": profile.__dict__},
        )
    volume = min(50, len(verified) * 8)
    ratings = []
    for item in verified:
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
        evidence=[evidence(item["url"], item.get("title") or item.get("snippet") or "") for item in verified[:8]],
        findings=[SubScoreFinding(severity="medium" if len(verified) < 2 else "low", text=f"{len(verified)} verified public review-surface matches were found with an inferred average rating of {avg:.1f}/5.")],
        raw_data={"hits": verified, "raw_candidates": hits, "ratings": ratings, "average_rating": avg, "entity_profile": profile.__dict__},
    )
