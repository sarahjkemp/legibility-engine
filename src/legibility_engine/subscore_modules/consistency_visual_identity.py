from __future__ import annotations

from ..collectors.search import search_web, verify_entity_matches
from ..collectors.site import fetch_page
from ..config import AuditConfig, EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, root_domain


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    primary = await fetch_page(str(target.primary_url), settings)
    profile = build_entity_profile(target)
    surfaces = [primary]
    linkedin_surface = None
    try:
        hits = await search_web(f'site:linkedin.com/company "{target.company_name}"', settings, limit=1)
        verified_hits = await verify_entity_matches(hits, profile, settings)
        if verified_hits:
            linkedin_surface = verified_hits[0]
    except Exception:
        linkedin_surface = None
    matches = 1
    if linkedin_surface:
        matches += 1
    score = 100.0 if matches >= 3 else 65.0 if matches == 2 else 30.0
    return SubScoreResult(
        score=score,
        confidence=0.45,
        evidence=[evidence(primary["url"], primary["metadata"].get("og:site_name") or primary["metadata"].get("title") or root_domain(str(target.primary_url)))] + ([evidence(linkedin_surface["url"], linkedin_surface.get("title") or "")] if linkedin_surface else []),
        findings=[SubScoreFinding(severity="low" if matches >= 2 else "medium", text=f"Visual/identity stability check matched across {matches} sampled public surfaces.")],
        raw_data={"primary_metadata": primary["metadata"], "linkedin_surface": linkedin_surface, "entity_profile": profile.__dict__},
    )
