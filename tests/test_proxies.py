from types import SimpleNamespace

import pytest

from legibility_engine.config import load_audit_config
from legibility_engine.entity import assess_entity_match, build_entity_profile
from legibility_engine.models import AuditTarget
from legibility_engine.subscore_modules import authority_bodies, authority_tier1, behavioural_complaints, behavioural_fulfillment, behavioural_reviews, consistency_founder_voice, consistency_visual_identity, consistency_vocabulary_recurrence
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


@pytest.mark.anyio
async def test_behavioural_review_evidence_filters_unrelated_hits(monkeypatch) -> None:
    async def fake_search_web(query: str, settings, limit: int = 2) -> list[dict]:
        return [
            {"title": "St. John Knits | Timeless Luxury", "snippet": "", "url": "https://stjohnknits.com/", "domain": "stjohnknits.com", "registered_domain": "stjohnknits.com"},
            {"title": "Slumberjack | Outdoor Gear", "snippet": "", "url": "https://slumberjack.com/", "domain": "slumberjack.com", "registered_domain": "slumberjack.com"},
        ]

    async def fake_verify(results: list[dict], profile, settings) -> list[dict]:
        return []

    monkeypatch.setattr(behavioural_reviews, "search_web", fake_search_web)
    monkeypatch.setattr(behavioural_reviews, "verify_entity_matches", fake_verify)

    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led", sector="consultancy")
    result = await behavioural_reviews.run(target, load_audit_config(), SimpleNamespace())
    assert result.evidence == []
    assert result.score is None


@pytest.mark.anyio
async def test_behavioural_complaint_evidence_filters_sports_team_hits(monkeypatch) -> None:
    async def fake_search_web(query: str, settings, limit: int = 3) -> list[dict]:
        return [
            {"title": "SJK live score, schedule & player stats", "snippet": "Sofascore", "url": "https://www.sofascore.com/football/team/sjk/22395", "domain": "sofascore.com", "registered_domain": "sofascore.com"},
        ]

    async def fake_verify(results: list[dict], profile, settings) -> list[dict]:
        return []

    monkeypatch.setattr(behavioural_complaints, "search_web", fake_search_web)
    monkeypatch.setattr(behavioural_complaints, "verify_entity_matches", fake_verify)

    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led", sector="consultancy")
    result = await behavioural_complaints.run(target, load_audit_config(), SimpleNamespace())
    assert result.evidence == []
    assert result.raw_data["hits"] == []


@pytest.mark.anyio
async def test_visual_identity_rejects_unverified_linkedin_substitute(monkeypatch) -> None:
    async def fake_fetch_page(url: str, settings) -> dict:
        return {
            "url": url,
            "metadata": {"og:site_name": "SJK Labs", "title": "SJK Labs | Narrative architecture"},
            "text": "SJK Labs narrative architecture",
            "links": [],
            "structured_data": {},
        }

    async def fake_search_web(query: str, settings, limit: int = 1) -> list[dict]:
        return [{"title": "St. John Knits | Timeless Luxury", "snippet": "", "url": "https://stjohnknits.com/", "domain": "stjohnknits.com", "registered_domain": "stjohnknits.com"}]

    async def fake_verify(results: list[dict], profile, settings) -> list[dict]:
        return []

    monkeypatch.setattr(consistency_visual_identity, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(consistency_visual_identity, "search_web", fake_search_web)
    monkeypatch.setattr(consistency_visual_identity, "verify_entity_matches", fake_verify)

    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led", sector="consultancy")
    result = await consistency_visual_identity.run(target, load_audit_config(), SimpleNamespace())
    assert len(result.evidence) == 1
    assert result.score == 30.0


@pytest.mark.anyio
async def test_authority_bodies_reject_unverified_results(monkeypatch) -> None:
    async def fake_fetch_internal_pages(url: str, settings, limit: int = 4) -> list[dict]:
        return [{"text": "Member of PRCA and CIPR", "url": url}]

    async def fake_search_web(query: str, settings, limit: int = 3) -> list[dict]:
        return [{"title": "PRCA unrelated directory", "snippet": "", "url": "https://example.com/prca", "domain": "example.com", "registered_domain": "example.com"}]

    async def fake_verify(results: list[dict], profile, settings) -> list[dict]:
        return []

    monkeypatch.setattr(authority_bodies, "fetch_internal_pages", fake_fetch_internal_pages)
    monkeypatch.setattr(authority_bodies, "search_web", fake_search_web)
    monkeypatch.setattr(authority_bodies, "verify_entity_matches", fake_verify)

    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led", sector="consultancy")
    result = await authority_bodies.run(target, load_audit_config(), SimpleNamespace())
    assert result.score == 0.0
    assert result.evidence == []


@pytest.mark.anyio
async def test_vocabulary_recurrence_includes_verified_platform_surfaces(monkeypatch) -> None:
    async def fake_sampled_pages(target, settings, limit: int = 10) -> list[dict]:
        return [{"url": "https://sjklabs.co", "text": "The legibility gap narrative strategy for the agent era. " * 12}]

    async def fake_platforms(target, settings) -> dict[str, list[dict]]:
        return {
            "substack": [{"url": "https://example.substack.com/p/post", "title": "SJK Labs on the legibility gap", "snippet": "Narrative strategy for the agent era"}],
            "medium": [{"url": "https://medium.com/@sarahkemp/post", "title": "SJK Labs and authority building", "snippet": "The legibility gap appears again"}],
        }

    monkeypatch.setattr(consistency_vocabulary_recurrence, "sampled_pages", fake_sampled_pages)
    monkeypatch.setattr(consistency_vocabulary_recurrence, "discover_platform_surfaces", fake_platforms)

    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led", sector="consultancy")
    result = await consistency_vocabulary_recurrence.run(target, load_audit_config(), SimpleNamespace(anthropic_api_key=None))
    assert "platform_surfaces" in result.raw_data
    assert result.raw_data["platform_surfaces"]["substack"][0]["url"].startswith("https://example.substack.com")


@pytest.mark.anyio
async def test_founder_voice_includes_platform_surfaces(monkeypatch) -> None:
    async def fake_sampled_pages(target, settings, limit: int = 6) -> list[dict]:
        return [{"url": "https://sjklabs.co", "text": "SJK Labs helps brands with legibility and narrative strategy. " * 8}]

    async def fake_get_text(url: str, settings, cache_namespace: str = "") -> str:
        return "Sarah Kemp writes about SJK Labs, legibility, and authority."

    async def fake_platforms(target, settings) -> dict[str, list[dict]]:
        return {"youtube": [{"url": "https://youtube.com/watch?v=123", "title": "Sarah Kemp on SJK Labs", "snippet": "Narrative architecture interview"}]}

    async def fake_search_web(query: str, settings, limit: int = 6) -> list[dict]:
        return []

    monkeypatch.setattr(consistency_founder_voice, "sampled_pages", fake_sampled_pages)
    monkeypatch.setattr(consistency_founder_voice, "get_text", fake_get_text)
    monkeypatch.setattr(consistency_founder_voice, "discover_platform_surfaces", fake_platforms)
    monkeypatch.setattr(consistency_founder_voice, "search_web", fake_search_web)

    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led", sector="consultancy", founder_name="Sarah Kemp", founder_linkedin_url="https://linkedin.com/in/sarahjkemp")
    result = await consistency_founder_voice.run(target, load_audit_config(), SimpleNamespace(anthropic_api_key=None))
    assert "platform_surfaces" in result.raw_data
    assert any(item.source.startswith("https://youtube.com") for item in result.evidence)


@pytest.mark.anyio
async def test_fulfillment_uses_platform_hosted_owned_surfaces(monkeypatch) -> None:
    async def fake_fetch_internal_pages(url: str, settings, limit: int = 10) -> list[dict]:
        return []

    async def fake_platforms(target, settings) -> dict[str, list[dict]]:
        return {
            "youtube": [{"url": "https://youtube.com/watch?v=123", "title": "Client growth case study", "snippet": "How SJK Labs helped a client grow"}]
        }

    monkeypatch.setattr(behavioural_fulfillment, "fetch_internal_pages", fake_fetch_internal_pages)
    monkeypatch.setattr(behavioural_fulfillment, "discover_platform_surfaces", fake_platforms)

    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led", sector="consultancy")
    result = await behavioural_fulfillment.run(target, load_audit_config(), SimpleNamespace())
    assert result.score == 100.0
    assert any(item.source.startswith("https://youtube.com") for item in result.evidence)
