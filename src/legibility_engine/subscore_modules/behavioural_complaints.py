from __future__ import annotations

from ..collectors.search import dedupe_by_registered_domain, search_web, verify_entity_matches
from ..config import AuditConfig, EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    profile = build_entity_profile(target)
    queries = [f'"{target.company_name}" complaint', f'"{target.company_name}" scam', f'"{target.company_name}" reddit']
    hits = []
    for query in queries:
        hits.extend(await search_web(query, settings, limit=3))
    verified = dedupe_by_registered_domain(await verify_entity_matches(hits, profile, settings))
    if not verified:
        return SubScoreResult(score=95.0, confidence=0.4, findings=[SubScoreFinding(severity="low", text="No verified complaint or dispute surfaces were found in the sampled public search results.")], raw_data={"hits": [], "raw_candidates": hits, "entity_profile": profile.__dict__})
    serious = 0
    for item in verified:
        snippet = " ".join([item.get("title", ""), item.get("snippet", "")]).lower()
        if any(term in snippet for term in ["fraud", "scam", "lawsuit", "complaint", "tribunal"]):
            serious += 1
    deduction = min(70, serious * 15)
    score = max(20.0, 100.0 - deduction)
    return SubScoreResult(
        score=score,
        confidence=0.55,
        evidence=[evidence(item["url"], item.get("title") or item.get("snippet") or "") for item in verified[:8]],
        findings=[SubScoreFinding(severity="medium" if serious else "low", text=f"{serious} potentially material complaint/dispute signals were found in verified public results.")],
        raw_data={"hits": verified, "raw_candidates": hits, "serious_count": serious, "entity_profile": profile.__dict__},
    )
