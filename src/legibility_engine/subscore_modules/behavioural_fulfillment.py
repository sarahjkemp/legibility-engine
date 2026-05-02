from __future__ import annotations

from ..collectors.platform_surfaces import discover_platform_surfaces
from ..collectors.site import fetch_internal_pages
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await fetch_internal_pages(str(target.primary_url), settings, limit=10)
    candidate_pages = [page for page in pages if any(term in page["url"].lower() for term in ["case", "client", "work", "results", "testimonial"])]
    platform_surfaces = await discover_platform_surfaces(target, settings)
    platform_candidates = [
        item
        for items in platform_surfaces.values()
        for item in items
        if any(
            term in (((item.get("title") or "") + " " + (item.get("snippet") or "")).lower())
            for term in ["client", "case", "result", "growth", "podcast", "interview"]
        )
    ]
    if not candidate_pages and not platform_candidates:
        return SubScoreResult(score=0.0, confidence=0.6, findings=[SubScoreFinding(severity="medium", text="No obvious case study, client proof, or platform-hosted evidence surfaces were found.")], raw_data={"candidate_pages": [], "platform_candidates": []})
    strong = []
    for page in candidate_pages:
        text = page.get("text", "").lower()
        if any(term in text for term in ["%", "increase", "growth", "revenue", "pipeline", "named client", "worked with"]):
            strong.append(page)
    strong_platform = [
        item for item in platform_candidates
        if any(term in ((item.get("snippet") or "") + " " + (item.get("title") or "")).lower() for term in ["client", "%", "growth", "result", "case study", "interview"])
    ]
    total_candidates = len(candidate_pages) + len(platform_candidates)
    total_strong = len(strong) + len(strong_platform)
    score = round((total_strong / total_candidates) * 100, 2) if total_candidates else 0.0
    return SubScoreResult(
        score=score,
        confidence=0.7,
        evidence=[evidence(page["url"], page.get("metadata", {}).get("title") or page.get("text", "")[:180]) for page in strong[:8]]
        + [evidence(item["url"], item.get("snippet") or item.get("title") or "") for item in strong_platform[:8]],
        findings=[SubScoreFinding(severity="medium" if score < 50 else "low", text=f"{total_strong} of {total_candidates} sampled owned or platform-hosted proof surfaces included more than a logo-wall level of fulfilment evidence.")],
        raw_data={"candidate_pages": [page["url"] for page in candidate_pages], "strong_pages": [page["url"] for page in strong], "platform_surfaces": platform_surfaces, "platform_candidates": [item["url"] for item in platform_candidates], "strong_platform": [item["url"] for item in strong_platform]},
    )
