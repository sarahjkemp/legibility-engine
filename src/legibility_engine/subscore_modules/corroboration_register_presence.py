from __future__ import annotations

from ..collectors.companies_house import fetch_company_profile, search_companies_house
from ..collectors.search import search_web, verify_entity_matches
from ..collectors.wikidata import lookup_entity
from ..config import AuditConfig, EngineSettings
from ..entity import build_entity_profile
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    entity_profile = build_entity_profile(target)
    companies = await search_companies_house(target.company_name, settings, limit=3)
    company_profile = await fetch_company_profile(companies[0]["url"], settings) if companies else None
    wikidata = await lookup_entity(target.company_name, settings, limit=3)
    linkedin_candidates = await search_web(f'site:linkedin.com/company "{target.company_name}"', settings, limit=3)
    crunchbase_candidates = await search_web(f'site:crunchbase.com/organization "{target.company_name}"', settings, limit=3)
    linkedin_hits = await verify_entity_matches(linkedin_candidates, entity_profile, settings)
    crunchbase_hits = await verify_entity_matches(crunchbase_candidates, entity_profile, settings)

    register_count = int(bool(companies)) + int(bool(wikidata)) + int(bool(linkedin_hits or crunchbase_hits))
    score = 0.0 if register_count == 0 else 40.0 if register_count == 1 else 70.0 if register_count == 2 else 100.0
    evidence_items = []
    if companies:
        evidence_items.append(evidence(companies[0]["url"], companies[0]["description"]))
    if company_profile:
        evidence_items.append(evidence(company_profile["url"], company_profile.get("registered_address") or company_profile.get("page_text", "")[:200]))
    if wikidata:
        evidence_items.append(evidence(wikidata[0]["url"], f'Wikidata entity {wikidata[0]["id"]}: {wikidata[0]["label"]}'))
    if linkedin_hits:
        evidence_items.append(evidence(linkedin_hits[0]["url"], linkedin_hits[0]["title"]))
    if crunchbase_hits:
        evidence_items.append(evidence(crunchbase_hits[0]["url"], crunchbase_hits[0]["title"]))

    return SubScoreResult(
        score=score,
        confidence=0.8 if register_count >= 2 else 0.6,
        evidence=evidence_items,
        findings=[SubScoreFinding(severity="low" if register_count >= 2 else "medium", text=f"{register_count} third-party register surfaces were confirmed for the brand.")],
        raw_data={
            "companies_house_results": companies,
            "companies_house_profile": company_profile,
            "wikidata": wikidata,
            "linkedin_candidates": linkedin_candidates,
            "linkedin_hits": linkedin_hits,
            "crunchbase_candidates": crunchbase_candidates,
            "crunchbase_hits": crunchbase_hits,
        },
    )
