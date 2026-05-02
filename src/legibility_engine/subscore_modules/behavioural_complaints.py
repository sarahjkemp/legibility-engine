from __future__ import annotations

from ..collectors.search import search_web
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    queries = [f'"{target.company_name}" complaint', f'"{target.company_name}" scam', f'"{target.company_name}" reddit']
    hits = []
    for query in queries:
        hits.extend(await search_web(query, settings, limit=3))
    if not hits:
        return SubScoreResult(score=95.0, confidence=0.4, findings=[SubScoreFinding(severity="low", text="No obvious complaint or dispute surfaces were found in the sampled public search results.")], raw_data={"hits": []})
    serious = 0
    for item in hits:
        snippet = " ".join([item.get("title", ""), item.get("snippet", "")]).lower()
        if any(term in snippet for term in ["fraud", "scam", "lawsuit", "complaint", "tribunal"]):
            serious += 1
    deduction = min(70, serious * 15)
    score = max(20.0, 100.0 - deduction)
    return SubScoreResult(
        score=score,
        confidence=0.55,
        evidence=[evidence(item["url"], item.get("title") or item.get("snippet") or "") for item in hits[:8]],
        findings=[SubScoreFinding(severity="medium" if serious else "low", text=f"{serious} potentially material complaint/dispute signals were found in sampled public results.")],
        raw_data={"hits": hits, "serious_count": serious},
    )
