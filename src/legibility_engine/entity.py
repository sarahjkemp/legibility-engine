from __future__ import annotations

import re
from dataclasses import dataclass

from .matching import get_registered_domain, is_strict_brand_match, normalize_brand_text
from .models import AuditTarget

SECTOR_KEYWORDS = {
    "b2b_saas": {"software", "platform", "api", "payments", "saas", "product", "developer"},
    "professional_services": {"agency", "consultancy", "advisory", "marketing", "communications", "clients"},
    "consultancy": {"consultancy", "consulting", "strategy", "advisor", "advisory", "clients"},
    "other": set(),
}


@dataclass(frozen=True)
class EntityProfile:
    company_name: str
    canonical_brand: str
    registered_domain: str
    founder_name: str | None
    companies_house_id: str | None
    sector: str
    ambiguous_name: bool


@dataclass(frozen=True)
class EntityMatch:
    decision: str
    confidence: float
    signals: tuple[str, ...]
    reasons: tuple[str, ...]


def build_entity_profile(target: AuditTarget) -> EntityProfile:
    canonical = normalize_brand_text(target.company_name)
    registered_domain = get_registered_domain(str(target.primary_url))
    return EntityProfile(
        company_name=target.company_name,
        canonical_brand=canonical,
        registered_domain=registered_domain,
        founder_name=target.founder_name,
        companies_house_id=target.companies_house_id,
        sector=target.sector,
        ambiguous_name=_is_ambiguous_brand(canonical),
    )


def assess_entity_match(
    profile: EntityProfile,
    *,
    title: str = "",
    snippet: str = "",
    page_text: str = "",
    url: str = "",
) -> EntityMatch:
    combined = " ".join(part for part in [title, snippet, page_text] if part)
    signals: list[str] = []
    reasons: list[str] = []

    if is_strict_brand_match(profile.company_name, combined):
        signals.append("full_brand_name")
        reasons.append("Full canonical brand name appears in the sampled text.")

    if profile.founder_name and is_strict_brand_match(profile.founder_name, combined):
        signals.append("founder_name")
        reasons.append("Founder name appears alongside the brand context.")

    if profile.companies_house_id and profile.companies_house_id in combined:
        signals.append("company_id")
        reasons.append("Companies House identifier appears in the sampled text.")

    if profile.registered_domain and profile.registered_domain in combined.lower():
        signals.append("official_domain_reference")
        reasons.append("The audited domain is referenced in the sampled text.")

    if _has_sector_signal(profile.sector, combined):
        signals.append("sector_context")
        reasons.append("The surrounding text matches the audited sector context.")

    if url and profile.registered_domain and profile.registered_domain == get_registered_domain(url):
        signals.append("owned_domain")
        reasons.append("The URL is the audited owned domain.")

    if "full_brand_name" not in signals:
        return EntityMatch("not_match", 0.0, tuple(signals), tuple(reasons or ["Full brand name was not found."]))

    secondary = [signal for signal in signals if signal != "full_brand_name"]
    if profile.ambiguous_name and not secondary:
        return EntityMatch(
            "possible_match",
            0.45,
            tuple(signals),
            tuple(reasons + ["Brand name is ambiguous, so a second confirming signal is required."]),
        )

    confidence = 0.7 if not profile.ambiguous_name else 0.85 if secondary else 0.45
    return EntityMatch("verified_match", confidence, tuple(signals), tuple(reasons))


def _is_ambiguous_brand(canonical_brand: str) -> bool:
    tokens = canonical_brand.split()
    compact = canonical_brand.replace(" ", "")
    if len(tokens) <= 2 and len(compact) <= 8:
        return True
    if any(re.fullmatch(r"[a-z]{1,4}", token) for token in tokens):
        return True
    if re.fullmatch(r"[a-z]{2,5}\d?", compact):
        return True
    return False


def _has_sector_signal(sector: str, text: str) -> bool:
    keywords = SECTOR_KEYWORDS.get(sector, set())
    if not keywords:
        return False
    normalized = normalize_brand_text(text)
    return any(re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", normalized) for keyword in keywords)
