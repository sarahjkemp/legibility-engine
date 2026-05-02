from __future__ import annotations

from ..collectors.site import fetch_internal_pages
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await fetch_internal_pages(str(target.primary_url), settings, limit=10)
    candidate_pages = [page for page in pages if any(term in page["url"].lower() for term in ["case", "client", "work", "results", "testimonial"])]
    if not candidate_pages:
        return SubScoreResult(score=0.0, confidence=0.6, findings=[SubScoreFinding(severity="medium", text="No obvious case study or client proof pages were surfaced on the owned domain sample.")], raw_data={"candidate_pages": []})
    strong = []
    for page in candidate_pages:
        text = page.get("text", "").lower()
        if any(term in text for term in ["%", "increase", "growth", "revenue", "pipeline", "named client", "worked with"]):
            strong.append(page)
    score = round((len(strong) / len(candidate_pages)) * 100, 2)
    return SubScoreResult(
        score=score,
        confidence=0.7,
        evidence=[evidence(page["url"], page.get("metadata", {}).get("title") or page.get("text", "")[:180]) for page in strong[:8]],
        findings=[SubScoreFinding(severity="medium" if score < 50 else "low", text=f"{len(strong)} of {len(candidate_pages)} sampled proof pages included more than a logo-wall level of fulfilment evidence.")],
        raw_data={"candidate_pages": [page["url"] for page in candidate_pages], "strong_pages": [page["url"] for page in strong]},
    )
