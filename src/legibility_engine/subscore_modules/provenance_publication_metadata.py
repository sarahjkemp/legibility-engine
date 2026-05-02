from __future__ import annotations

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, sampled_pages


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await sampled_pages(target, settings, limit=20)
    substantive = [page for page in pages if len(page.get("text", "").split()) >= 120]
    if not substantive:
        return SubScoreResult(score=None, confidence=0.0, findings=[SubScoreFinding(severity="medium", text="No substantive pages were available for metadata checks.")], raw_data={"pages": []})
    complete = []
    for page in substantive:
        metadata = page.get("metadata", {})
        checks = [
            bool(metadata.get("article:published_time")),
            bool(metadata.get("article:modified_time")),
            bool(metadata.get("og:title")),
            bool(metadata.get("canonical_url")),
            "Article" in str(page.get("structured_data", {})),
        ]
        if sum(checks) >= 3:
            complete.append(page)
    score = round((len(complete) / len(substantive)) * 100, 2)
    return SubScoreResult(
        score=score,
        confidence=0.85,
        evidence=[evidence(page["url"], str(page.get("metadata", {}))) for page in complete[:6]],
        findings=[SubScoreFinding(severity="medium" if score < 60 else "low", text=f"{len(complete)} of {len(substantive)} substantive pages exposed materially complete publication metadata.")],
        raw_data={"substantive_pages": [page["url"] for page in substantive], "complete_pages": [page["url"] for page in complete]},
    )
