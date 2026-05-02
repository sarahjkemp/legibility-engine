from types import SimpleNamespace

import pytest

from legibility_engine.config import load_audit_config
from legibility_engine.entity import assess_entity_match, build_entity_profile
from legibility_engine.models import AuditTarget
from legibility_engine.subscore_modules import authority_tier1
from legibility_engine.collectors.search import (
    dedupe_by_registered_domain,
    filter_to_registered_domain_allowlist,
)


@pytest.mark.anyio
async def test_tier1_rejects_false_positive_initialism_match(monkeypatch) -> None:
    async def fake_search_web(query: str, settings, limit: int = 2) -> list[dict]:
        return [
            {
                "title": "St. John Knits launches new collection",
                "url": "https://stjohnknits.com/story",
                "domain": "stjohnknits.com",
                "registered_domain": "stjohnknits.com",
                "snippet": "Luxury knitwear update.",
            }
        ]

    async def fake_verify(results: list[dict], profile, settings) -> list[dict]:
        verified = []
        for item in results:
            match = assess_entity_match(profile, title=item["title"], snippet=item["snippet"], url=item["url"])
            if match.decision == "verified_match":
                verified.append(item)
        return verified

    monkeypatch.setattr(authority_tier1, "search_web", fake_search_web)
    monkeypatch.setattr(authority_tier1, "verify_entity_matches", fake_verify)

    config = load_audit_config()
    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led")
    settings = SimpleNamespace()

    result = await authority_tier1.run(target, config, settings)

    assert result.score == 0.0


def test_strict_brand_match_only_counts_full_canonical_brand_name() -> None:
    target = AuditTarget(
        company_name="Form3",
        primary_url="https://form3.tech",
        audit_type="b2b_saas",
        sector="b2b_saas",
    )
    profile = build_entity_profile(target)
    verified = assess_entity_match(
        profile,
        title="Form3 raises funding for payments infrastructure",
        snippet="The cloud payments platform expands.",
        url="https://form3.tech/news",
    )
    rejected = assess_entity_match(
        profile,
        title="Form3 design festival launches",
        snippet="A visual arts collective expands its residency program.",
        url="https://form3.com/blog",
    )
    assert verified.decision == "verified_match"
    assert rejected.decision != "verified_match"


def test_dedupe_by_registered_domain_counts_same_domain_once() -> None:
    results = [
        {"url": f"https://ft.com/article-{index}", "domain": "ft.com", "registered_domain": "ft.com", "title": "FT mention", "snippet": "SJK Labs"}
        for index in range(9)
    ]
    deduped = dedupe_by_registered_domain(results)
    assert len(deduped) == 1


def test_allowlist_filters_out_non_tier_domain() -> None:
    results = [
        {
            "title": "SJK Labs featured",
            "url": "https://stjohnknits.com/story",
            "domain": "stjohnknits.com",
            "registered_domain": "stjohnknits.com",
            "snippet": "SJK Labs",
        }
    ]
    filtered = filter_to_registered_domain_allowlist(results, {"ft.com", "bbc.co.uk"})
    assert filtered == []


def test_ambiguous_brand_requires_second_signal() -> None:
    target = AuditTarget(
        company_name="SJK Labs",
        primary_url="https://sjklabs.co",
        audit_type="founder_led",
        sector="consultancy",
        founder_name="Sarah Kemp",
    )
    profile = build_entity_profile(target)
    possible = assess_entity_match(
        profile,
        title="SJK Labs launches something",
        snippet="A company has launched something.",
        url="https://example.com/story",
    )
    verified = assess_entity_match(
        profile,
        title="SJK Labs launches new legibility audit",
        snippet="Founder Sarah Kemp said the consultancy is focused on narrative strategy.",
        url="https://example.com/story",
    )
    assert possible.decision == "possible_match"
    assert verified.decision == "verified_match"
