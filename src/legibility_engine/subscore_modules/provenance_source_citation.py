from __future__ import annotations

from urllib.parse import urlparse

from ..collectors.anthropic_client import AnthropicJSONClient
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, root_domain, sampled_pages

SOCIAL = {"linkedin.com", "x.com", "twitter.com", "facebook.com", "instagram.com", "youtube.com"}


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await sampled_pages(target, settings, limit=12)
    owned = root_domain(str(target.primary_url))
    substantive = [page for page in pages if len(page.get("text", "").split()) >= 120]
    if not substantive:
        return SubScoreResult(score=None, confidence=0.0, findings=[SubScoreFinding(severity="medium", text="No substantive pages were available to inspect source links.")], raw_data={"pages": []})

    page_payload = []
    for page in substantive[:8]:
        outbound = []
        for link in page.get("links", []):
            domain = urlparse(link).netloc.replace("www.", "")
            if not domain or domain == owned or domain.endswith(f".{owned}") or domain in SOCIAL:
                continue
            outbound.append(link)
        page_payload.append({"url": page["url"], "outbound_links": outbound[:10]})

    evidence_counts = []
    llm = AnthropicJSONClient(settings)
    classifications = []
    if llm.available:
        try:
            payload = {"pages": page_payload}
            result = await llm.run_prompt(config.prompt_dir / "source_link_classification_v1.md", payload)
            classifications = result.get("links", []) if isinstance(result, dict) else []
        except Exception:
            classifications = []
    if classifications:
        by_url = {}
        for item in classifications:
            by_url.setdefault(item.get("url"), []).append(item)
        for page in page_payload:
            evidence_counts.append(sum(1 for item in by_url.get(page["url"], []) if item.get("classification") == "evidence"))
    else:
        for page in page_payload:
            evidence_counts.append(min(3, len(page["outbound_links"])))

    avg_links = sum(evidence_counts) / len(evidence_counts) if evidence_counts else 0.0
    score = 0.0 if avg_links == 0 else 50.0 if avg_links < 3 else 100.0
    return SubScoreResult(
        score=score,
        confidence=0.75 if classifications else 0.6,
        evidence=[evidence(page["url"], f"{count} evidence-like outbound links") for page, count in zip(page_payload, evidence_counts, strict=False) if count],
        findings=[SubScoreFinding(severity="medium" if avg_links < 1 else "low", text=f"Sampled substantive pages averaged {avg_links:.1f} evidence-like outbound links.")],
        raw_data={"pages": page_payload, "classifications": classifications, "evidence_counts": evidence_counts},
    )
