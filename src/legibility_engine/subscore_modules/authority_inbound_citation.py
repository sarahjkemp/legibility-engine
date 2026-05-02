from __future__ import annotations

from ..collectors.openpagerank import lookup_domains
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings, authority_domains: list[str]) -> SubScoreResult:
    if not authority_domains:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="No authoritative domains were surfaced to estimate inbound citation strength.")],
            raw_data={"authority_domains": []},
        )
    opr = await lookup_domains(authority_domains, settings)
    if not opr:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="Inbound citation estimate is unavailable without Open PageRank responses.")],
            raw_data={"authority_domains": authority_domains, "openpagerank": {}},
        )
    mean_rank = sum(float((data.get("page_rank_decimal") or 0)) for data in opr.values()) / max(1, len(opr))
    score = round(min(100.0, mean_rank * 12), 2)
    return SubScoreResult(
        score=score,
        confidence=0.35,
        evidence=[evidence(f"https://{domain}", f"Authority-domain rank proxy {data.get('page_rank_decimal')}") for domain, data in list(opr.items())[:8]],
        findings=[SubScoreFinding(severity="low", text="Inbound citation from authoritative sources remains a low-confidence free-data estimate in v1.")],
        raw_data={"authority_domains": authority_domains, "openpagerank": opr},
    )
