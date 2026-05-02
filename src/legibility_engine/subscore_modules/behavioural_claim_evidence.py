from __future__ import annotations

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.site import fetch_internal_pages
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await fetch_internal_pages(str(target.primary_url), settings, limit=8)
    relevant = [page for page in pages if page["url"] == str(target.primary_url) or any(term in page["url"].lower() for term in ["service", "work", "offer", "about"])]
    combined = "\n\n".join(page.get("text", "")[:2500] for page in relevant[:5])
    llm = AnthropicJSONClient(settings)
    claims = []
    if llm.available:
        try:
            result = await llm.run_prompt(config.prompt_dir / "claim_evidence_ratio_v1.md", {"text": combined[:12000]})
            claims = result.get("claims", []) if isinstance(result, dict) else []
        except Exception:
            claims = []
    if not claims:
        rough_claims = [sentence.strip() for sentence in combined.split(".") if sentence.strip()][:8]
        claims = [{"claim": claim[:180], "evidence_present": any(token in claim.lower() for token in ["case study", "%", "client", "result"]), "evidence_excerpt": claim[:220]} for claim in rough_claims]
    backed = sum(1 for item in claims if item.get("evidence_present"))
    score = round((backed / len(claims)) * 100, 2) if claims else None
    return SubScoreResult(
        score=score,
        confidence=0.8 if claims else 0.5,
        evidence=[evidence(str(target.primary_url), item.get("evidence_excerpt") or item.get("claim") or "") for item in claims[:8]],
        findings=[SubScoreFinding(severity="medium" if (score or 0) < 50 else "low", text=f"{backed} of {len(claims)} sampled claims were accompanied by visible evidence on owned surfaces.")],
        raw_data={"claims": claims, "pages": [page["url"] for page in relevant[:5]]},
    )
