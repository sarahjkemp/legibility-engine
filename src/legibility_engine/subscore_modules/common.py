from __future__ import annotations

import re
from urllib.parse import urlparse

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.site import fetch_internal_pages
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreEvidence


def root_domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def page_excerpt(text: str, limit: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]


def evidence(source: str, value: str) -> SubScoreEvidence:
    return SubScoreEvidence(source=source, value=value[:500])


async def sampled_pages(target: AuditTarget, settings: EngineSettings, limit: int = 20) -> list[dict]:
    return await fetch_internal_pages(str(target.primary_url), settings, limit=limit)


async def extract_claims(
    text: str,
    config: AuditConfig,
    settings: EngineSettings,
) -> list[dict]:
    llm = AnthropicJSONClient(settings)
    if llm.available:
        try:
            payload = {"text": text[:12000]}
            result = await llm.run_prompt(config.prompt_dir / "claim_extraction_v1.md", payload)
            claims = result.get("claims") if isinstance(result, dict) else None
            if isinstance(claims, list):
                return claims[:5]
        except Exception:
            pass
    claims: list[dict] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        candidate = sentence.strip()
        lowered = candidate.lower()
        if not candidate:
            continue
        if any(token in lowered for token in ["help", "work with", "founded", "audit", "strategy", "brand"]):
            claims.append({"claim": candidate[:180], "claim_type": "other", "supporting_excerpt": candidate[:220]})
        if len(claims) >= 5:
            break
    return claims
