from __future__ import annotations

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.search import search_web
from ..collectors.transport import get_text
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
    if not target.founder_name and not target.founder_linkedin_url:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No founder surface was provided for voice-consistency comparison.")],
            raw_data={},
        )
    pages = await sampled_pages(target, settings, limit=6)
    company_bio = "\n\n".join(page["text"][:1200] for page in pages[:2])
    founder_text = ""
    if target.founder_linkedin_url:
        try:
            founder_text = await get_text(str(target.founder_linkedin_url), settings, cache_namespace="founder_linkedin_pages")
        except Exception:
            founder_text = ""
    search_hits = await search_web(f'"{target.founder_name or ""}" "{target.company_name}" podcast OR article', settings, limit=6)
    external_snippets = "\n".join((item.get("snippet") or item.get("title") or "") for item in search_hits[:4])
    llm = AnthropicJSONClient(settings)
    verdict = "mixed"
    rationale = "Heuristic founder/company voice comparison."
    if llm.available:
        try:
            payload = {
                "founder_text": founder_text[:3000],
                "company_bio": company_bio[:3000],
                "external_snippets": external_snippets[:2000],
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
        evidence=[evidence(str(target.founder_linkedin_url or target.primary_url), (founder_text or company_bio)[:180])] + [evidence(item["url"], item.get("snippet") or item.get("title") or "") for item in search_hits[:3]],
        findings=[SubScoreFinding(severity="medium" if score < 75 else "low", text=rationale)],
        raw_data={"founder_text_excerpt": founder_text[:1200], "company_bio_excerpt": company_bio[:1200], "search_hits": search_hits, "verdict": verdict},
    )
