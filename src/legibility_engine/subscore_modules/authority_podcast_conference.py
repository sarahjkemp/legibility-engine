from __future__ import annotations

from ..collectors.search import dedupe_by_registered_domain, search_web, verify_entity_matches
from ..config import AuditConfig, EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    founder = target.founder_name or target.company_name
    profile = build_entity_profile(target)
    podcast_hits = await search_web(f'"{founder}" podcast', settings, limit=6)
    speaker_hits = await search_web(f'"{founder}" speaker', settings, limit=6)
    combined = await verify_entity_matches(podcast_hits + speaker_hits, profile, settings)
    deduped = dedupe_by_registered_domain(combined)
    count = len(deduped)
    score = 0.0 if count == 0 else 40.0 if count <= 2 else 70.0 if count <= 5 else 100.0
    return SubScoreResult(
        score=score,
        confidence=0.65 if founder else 0.4,
        evidence=[evidence(item["url"], item.get("title") or item.get("snippet") or "") for item in deduped[:8]],
        findings=[SubScoreFinding(severity="medium" if count == 0 else "low", text=f"{count} podcast or speaking-surface matches were verified with host URLs.")],
        raw_data={"podcast_hits": podcast_hits, "speaker_hits": speaker_hits, "verified_hits": deduped},
    )
