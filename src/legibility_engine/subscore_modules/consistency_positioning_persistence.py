from __future__ import annotations

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.site import fetch_page
from ..collectors.wayback import fetch_snapshots
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, page_excerpt


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    current = await fetch_page(str(target.primary_url), settings)
    snapshots = await fetch_snapshots(str(target.primary_url), settings)
    if not snapshots:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No historical Wayback snapshots were available for the requested windows.")],
            raw_data={"current": current["metadata"], "snapshots": []},
        )

    llm = AnthropicJSONClient(settings)
    score = None
    rationale = ""
    if llm.available:
        try:
            payload = {
                "current": {
                    "title": current["metadata"].get("title"),
                    "description": current["metadata"].get("meta_description"),
                    "text_excerpt": page_excerpt(current["text"], 1200),
                },
                "snapshots": snapshots,
            }
            result = await llm.run_prompt(config.prompt_dir / "consistency_v1.md", payload)
            if isinstance(result, dict):
                score = float(result.get("positioning_persistence_score")) if result.get("positioning_persistence_score") is not None else None
                rationale = result.get("rationale", "")
        except Exception:
            score = None
    if score is None:
        score = 75.0 if len(snapshots) >= 2 else 55.0
        rationale = "Heuristic fallback based on available archive continuity."
    return SubScoreResult(
        score=score,
        confidence=0.8,
        evidence=[evidence(snapshot["archive_url"], f'{snapshot["window_months"]} month snapshot') for snapshot in snapshots],
        findings=[SubScoreFinding(severity="low" if score >= 75 else "medium", text=rationale or "Historical snapshots were compared with the current positioning.")],
        raw_data={"current": current["metadata"], "snapshots": snapshots, "rationale": rationale},
    )
