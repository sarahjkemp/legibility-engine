from __future__ import annotations

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.platform_surfaces import discover_platform_surfaces
from ..collectors.transport import get_text
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, sampled_pages


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await sampled_pages(target, settings, limit=10)
    surfaces = [{"url": page["url"], "text": page["text"][:2500]} for page in pages[:6]]
    if target.founder_linkedin_url:
        try:
            founder_text = await get_text(str(target.founder_linkedin_url), settings, cache_namespace="founder_linkedin_pages")
            surfaces.append({"url": str(target.founder_linkedin_url), "text": founder_text[:2500]})
        except Exception:
            pass
    platform_surfaces = await discover_platform_surfaces(target, settings)
    for items in platform_surfaces.values():
        for item in items[:2]:
            snippet = item.get("snippet") or item.get("title") or ""
            surfaces.append({"url": item["url"], "text": snippet[:2500]})
    llm = AnthropicJSONClient(settings)
    phrases: list[str] = []
    if llm.available:
        try:
            result = await llm.run_prompt(config.prompt_dir / "signature_phrases_v1.md", {"surfaces": surfaces})
            phrases = result.get("phrases", []) if isinstance(result, dict) else []
        except Exception:
            phrases = []
    if not phrases:
        phrases = ["legibility gap", "authority", "narrative strategy", "agent era", target.company_name.lower()]
    recurring = 0
    phrase_hits = {}
    for phrase in phrases[:5]:
        hits = sum(1 for surface in surfaces if phrase.lower() in surface["text"].lower())
        phrase_hits[phrase] = hits
        if hits >= 3:
            recurring += 1
    score = round((recurring / max(1, min(5, len(phrases[:5])))) * 100, 2)
    return SubScoreResult(
        score=score,
        confidence=0.72 if phrases else 0.55,
        evidence=[evidence(surface["url"], surface["text"][:180]) for surface in surfaces[:6]],
        findings=[SubScoreFinding(severity="medium" if score < 50 else "low", text=f"{recurring} of the sampled signature phrases recurred across at least three surfaces.")],
        raw_data={"surfaces": [surface["url"] for surface in surfaces], "platform_surfaces": platform_surfaces, "phrases": phrases, "phrase_hits": phrase_hits},
    )
