from __future__ import annotations

from ..collectors.anthropic_client import AnthropicJSONClient
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, extract_claims, page_excerpt, sampled_pages


async def run(
    target: AuditTarget,
    config: AuditConfig,
    settings: EngineSettings,
    third_party_mentions: list[dict],
) -> SubScoreResult:
    pages = await sampled_pages(target, settings, limit=6)
    owned_text = "\n\n".join(page_excerpt(page.get("text", ""), 1500) for page in pages[:4])
    claims = await extract_claims(owned_text, config, settings)
    if not third_party_mentions:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No third-party mentions were available to compare against extracted core claims.")],
        raw_data={"claims": claims, "mentions": []},
    )

    llm = AnthropicJSONClient(settings)
    assessments = []
    if llm.available and claims:
        try:
            payload = {"claims": claims, "mentions": third_party_mentions[:8]}
            result = await llm.run_prompt(config.prompt_dir / "claim_consistency_v1.md", payload)
            assessments = result.get("assessments", []) if isinstance(result, dict) else []
        except Exception:
            assessments = []

    if not assessments:
        for mention in third_party_mentions[:8]:
            snippet = (mention.get("snippet") or "").lower()
            match_count = sum(1 for claim in claims if any(word in snippet for word in claim.get("claim", "").lower().split()[:5]))
            verdict = "matches" if match_count >= 2 else "partially_matches" if match_count == 1 else "ignores"
            assessments.append({"url": mention["url"], "verdict": verdict, "rationale": "Heuristic snippet comparison."})

    matched = sum(1 for item in assessments if item.get("verdict") in {"matches", "partially_matches"})
    score = round((matched / len(assessments)) * 100, 2) if assessments else None
    findings = [
        SubScoreFinding(
            severity="high" if (score or 0) < 40 else "medium" if (score or 0) < 70 else "low",
            text=f"{matched} of {len(assessments)} sampled third-party mentions reflected or partially reflected the brand's core claims.",
        )
    ]
    return SubScoreResult(
        score=score,
        confidence=0.8 if claims and assessments else 0.45,
        evidence=[evidence(item["url"], item.get("rationale", item.get("verdict", ""))) for item in assessments[:8]],
        findings=findings,
        raw_data={"claims": claims, "assessments": assessments},
    )
