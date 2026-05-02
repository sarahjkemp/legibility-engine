from __future__ import annotations

import re

from ..collectors.companies_house import fetch_company_profile, search_companies_house
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, sampled_pages


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await sampled_pages(target, settings, limit=4)
    footer_text = " ".join(page.get("text", "")[:1200] for page in pages[:2])
    company_number_match = re.search(r"\b\d{8}\b", footer_text)
    vat_match = re.search(r"\bGB\d{9,12}\b", footer_text)
    companies = await search_companies_house(target.company_name, settings, limit=3)
    verified = None
    if companies:
        verified = await fetch_company_profile(companies[0]["url"], settings)
    displayed = bool(company_number_match or vat_match)
    score = 100.0 if verified and displayed else 75.0 if verified else 50.0 if displayed else 0.0
    evidence_items = []
    if verified:
        evidence_items.append(evidence(verified["url"], verified.get("registered_address") or verified.get("page_text", "")[:180]))
    if company_number_match:
        evidence_items.append(evidence(str(target.primary_url), f"Company number displayed on owned site: {company_number_match.group(0)}"))
    if vat_match:
        evidence_items.append(evidence(str(target.primary_url), f"VAT number displayed on owned site: {vat_match.group(0)}"))
    return SubScoreResult(
        score=score,
        confidence=0.85 if verified else 0.6,
        evidence=evidence_items,
        findings=[SubScoreFinding(severity="medium" if score < 75 else "low", text="Corporate identity was checked against public company registration surfaces and the owned-site footer/About copy.")],
        raw_data={"footer_excerpt": footer_text[:500], "companies_house_results": companies, "companies_house_profile": verified},
    )
