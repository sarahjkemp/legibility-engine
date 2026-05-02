from __future__ import annotations

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.owned_channels import fetch_owned_channel_surfaces
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, sampled_pages

VERDICT_SCORES = {
    "highly_consistent": 100.0,
    "mostly_consistent": 75.0,
    "mixed": 50.0,
    "contradictory": 25.0,
}


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    spokesperson_name = target.spokesperson_name or target.founder_name
    spokesperson_linkedin = target.spokesperson_linkedin_url or target.founder_linkedin_url
    if not spokesperson_name and not spokesperson_linkedin:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No spokesperson surface was provided for voice-consistency comparison.")],
            raw_data={},
        )
    pages = await sampled_pages(target, settings, limit=6)
    company_bio = "\n\n".join(page["text"][:1200] for page in pages[:2])
    owned_surfaces = await fetch_owned_channel_surfaces(target, settings)
    spokesperson_surfaces = [item for item in owned_surfaces if item["role"] == "spokesperson"]
    founder_text = "\n".join(item.get("text", "")[:1500] for item in spokesperson_surfaces[:3])
    platform_snippets = "\n".join(item.get("text", "")[:500] or item.get("title", "") for item in spokesperson_surfaces[:4])
    llm = AnthropicJSONClient(settings)
    verdict = "mixed"
    rationale = "Heuristic spokesperson/company voice comparison."
    if llm.available:
        try:
            payload = {
                "founder_text": founder_text[:3000],
                "company_bio": company_bio[:3000],
                "external_snippets": platform_snippets[:2000],
            }
            result = await llm.run_prompt(config.prompt_dir / "founder_voice_consistency_v1.md", payload)
            if isinstance(result, dict):
                verdict = result.get("verdict", verdict)
                rationale = result.get("rationale", rationale)
        except Exception:
            pass
    score = VERDICT_SCORES.get(verdict, 50.0)
    return SubScoreResult(
        score=score,
        confidence=0.55,
        evidence=[evidence(str(spokesperson_linkedin or target.primary_url), (founder_text or company_bio)[:180])]
        + [evidence(item["url"], item.get("text", "")[:180] or item.get("title") or "") for item in spokesperson_surfaces[:4]],
        findings=[SubScoreFinding(severity="medium" if score < 75 else "low", text=rationale)],
        raw_data={"founder_text_excerpt": founder_text[:1200], "company_bio_excerpt": company_bio[:1200], "spokesperson_surfaces": [item["url"] for item in spokesperson_surfaces], "verdict": verdict},
    )
