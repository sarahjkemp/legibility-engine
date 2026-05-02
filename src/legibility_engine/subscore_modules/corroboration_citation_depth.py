from __future__ import annotations

from ..collectors.openpagerank import lookup_domains
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(
    target: AuditTarget,
    config: AuditConfig,
    settings: EngineSettings,
    domains: list[str],
    mentions: list[dict],
) -> SubScoreResult:
    if not domains:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No third-party domains were available for authority proxy lookup.")],
            raw_data={"domains": [], "openpagerank": {}},
        )
    opr = await lookup_domains(domains, settings)
    if not opr:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="Open PageRank data was unavailable for the sampled third-party domains.")],
            raw_data={"domains": domains, "openpagerank": {}},
        )
    weighted_total = 0.0
    for mention in mentions:
        domain = mention.get("domain")
        rank = (opr.get(domain) or {}).get("page_rank_decimal") or 0
        weighted_total += float(rank) * 10
    score = round(min(100.0, weighted_total / max(1, len(mentions))), 2)
    return SubScoreResult(
        score=score,
        confidence=0.55,
        evidence=[
            evidence(f"https://{domain}", f"Open PageRank {data.get('page_rank_decimal')} for {domain}")
            for domain, data in list(opr.items())[:8]
        ],
        findings=[SubScoreFinding(severity="low", text="Open PageRank was used as a lightweight free proxy for citation depth.")],
        raw_data={"domains": domains, "openpagerank": opr},
    )
