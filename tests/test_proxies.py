from types import SimpleNamespace

import pytest

from legibility_engine.config import load_audit_config
from legibility_engine.models import AuditTarget
from legibility_engine.subscore_modules import authority_tier1
from legibility_engine.collectors.search import (
    dedupe_by_registered_domain,
    filter_to_registered_domain_allowlist,
    is_strict_brand_match,
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

    async def fake_verify(results: list[dict], brand_name: str, settings) -> list[dict]:
        return [item for item in results if is_strict_brand_match(brand_name, " ".join([item["title"], item["snippet"]]))]

    monkeypatch.setattr(authority_tier1, "search_web", fake_search_web)
    monkeypatch.setattr(authority_tier1, "verify_brand_matches", fake_verify)

    config = load_audit_config()
    target = AuditTarget(company_name="SJK Labs", primary_url="https://sjklabs.co", audit_type="founder_led")
    settings = SimpleNamespace()

    result = await authority_tier1.run(target, config, settings)

    assert result.score == 0.0


def test_strict_brand_match_only_counts_full_canonical_brand_name() -> None:
    results = [
        {"title": "Form3 raises funding for payments infrastructure", "snippet": "", "url": "https://form3.tech/news", "domain": "form3.tech", "registered_domain": "form3.tech"},
        {"title": "Form 3 workout method expands globally", "snippet": "", "url": "https://form3.com/blog", "domain": "form3.com", "registered_domain": "form3.com"},
    ]
    matches = [item for item in results if is_strict_brand_match("Form3", " ".join([item["title"], item["snippet"]]))]
    assert [item["registered_domain"] for item in matches] == ["form3.tech"]
    assert not is_strict_brand_match("SJK Labs", "St John Knits Labs preview")


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
