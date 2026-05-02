from __future__ import annotations

import re

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, root_domain, sampled_pages


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await sampled_pages(target, settings, limit=20)
    substantive = [page for page in pages if len(page.get("text", "").split()) >= 120]
    if not substantive:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No substantive pages were available to test authored content.")],
            raw_data={"pages": []},
        )
    attributed = []
    for page in substantive:
        html = page.get("html", "")
        metadata = page.get("metadata", {})
        has_author = bool(metadata.get("author")) or "Person" in str(page.get("structured_data", {})) or bool(re.search(r"\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", html))
        has_linkedin = any("linkedin.com/in/" in link for link in page.get("links", []))
        if has_author and has_linkedin:
            attributed.append(page)
    score = round((len(attributed) / len(substantive)) * 100, 2)
    return SubScoreResult(
        score=score,
        confidence=0.8,
        evidence=[evidence(page["url"], page.get("metadata", {}).get("author") or "Named author and LinkedIn signal detected.") for page in attributed[:8]],
        findings=[SubScoreFinding(severity="medium" if score < 50 else "low", text=f"{len(attributed)} of {len(substantive)} substantive pages exposed attributable and verifiable authorship cues.")],
        raw_data={"substantive_pages": [page["url"] for page in substantive], "attributed_pages": [page["url"] for page in attributed], "owned_domain": root_domain(str(target.primary_url))},
    )
