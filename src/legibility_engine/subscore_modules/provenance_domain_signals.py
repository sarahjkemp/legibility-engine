from __future__ import annotations

from ..collectors.domain import lookup_domain_age_years
from ..collectors.site import fetch_page
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, root_domain


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    url = str(target.primary_url)
    domain = root_domain(url)
    page = await fetch_page(url, settings)
    domain_age = lookup_domain_age_years(domain)
    https_ok = url.startswith("https://")
    ssl_ok = https_ok and page.get("status_code") == 200
    if domain_age is None and not https_ok and not ssl_ok:
        return SubScoreResult(
            score=None,
            confidence=0.0,
            findings=[SubScoreFinding(severity="medium", text="Domain age and transport security signals were unavailable.")],
            raw_data={"domain": domain, "domain_age_years": None},
        )
    score = 100.0
    if domain_age is None or domain_age <= 5:
        score -= 25.0
    if not https_ok:
        score -= 25.0
    if not ssl_ok:
        score -= 25.0
    return SubScoreResult(
        score=max(0.0, score),
        confidence=0.75 if domain_age is not None else 0.55,
        evidence=[
            evidence(url, f"HTTPS enabled: {https_ok}; SSL request succeeded: {ssl_ok}"),
            evidence(f"https://{domain}", f"Estimated domain age: {domain_age if domain_age is not None else 'unavailable'} years"),
        ],
        findings=[SubScoreFinding(severity="medium" if score < 100 else "low", text="Domain age, HTTPS, and SSL validity were used as lightweight domain-authority signals.")],
        raw_data={"domain": domain, "domain_age_years": domain_age, "https_ok": https_ok, "ssl_ok": ssl_ok},
    )
