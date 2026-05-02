from __future__ import annotations

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.owned_channels import fetch_owned_channel_surfaces
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, sampled_pages


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await sampled_pages(target, settings, limit=10)
    surfaces = [{"url": page["url"], "text": page["text"][:2500]} for page in pages[:6]]
    owned_surfaces = await fetch_owned_channel_surfaces(target, settings)
    for item in owned_surfaces:
        if item["platform"] == "website":
            continue
        surfaces.append({"url": item["url"], "text": item.get("text", "")[:2500]})
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
    channel_snapshots = [
        {
            "role": item["role"],
            "platform": item["platform"],
            "url": item["url"],
            "excerpt": item.get("snapshot") or item.get("text", "")[:280],
        }
        for item in owned_surfaces
    ]
    return SubScoreResult(
        score=score,
        confidence=0.72 if phrases else 0.55,
        evidence=[evidence(surface["url"], surface["text"][:180]) for surface in surfaces[:6]],
        findings=[SubScoreFinding(severity="medium" if score < 50 else "low", text=f"{recurring} of the sampled signature phrases recurred across at least three surfaces.")],
        raw_data={
            "surfaces": [surface["url"] for surface in surfaces],
            "owned_channel_surfaces": [item["url"] for item in owned_surfaces],
            "channel_snapshots": channel_snapshots,
            "phrases": phrases,
            "phrase_hits": phrase_hits,
        },
    )
