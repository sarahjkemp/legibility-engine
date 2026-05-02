from __future__ import annotations

from .models import CoverageEntry, CoverageSummary, ProxyResult


def build_coverage_summary(proxy_results: list[ProxyResult]) -> CoverageSummary:
    entries: list[CoverageEntry] = []
    entries.extend(_coverage_from_provenance(_find_proxy(proxy_results, "provenance")))
    entries.extend(_coverage_from_consistency(_find_proxy(proxy_results, "consistency")))
    entries.extend(_coverage_from_corroboration(_find_proxy(proxy_results, "corroboration")))
    entries.extend(_coverage_from_authority(_find_proxy(proxy_results, "authority_hierarchy")))
    entries.extend(_coverage_from_behavioural(_find_proxy(proxy_results, "behavioural_reliability")))
    return CoverageSummary(
        checked=sum(1 for item in entries if item.status in {"checked", "found", "missing"}),
        found=sum(1 for item in entries if item.status == "found"),
        missing=sum(1 for item in entries if item.status == "missing"),
        unavailable=sum(1 for item in entries if item.status == "unavailable"),
        by_source_class=entries,
    )


def _find_proxy(proxy_results: list[ProxyResult], name: str) -> ProxyResult | None:
    return next((item for item in proxy_results if item.proxy_name == name), None)


def _coverage_from_provenance(proxy: ProxyResult | None) -> list[CoverageEntry]:
    if proxy is None:
        return []
    raw = proxy.raw_data
    metadata = raw.get("publication_metadata", {}).get("substantive_pages") or raw.get("metadata", {})
    structured_keys = raw.get("publication_metadata", {}).get("complete_pages") or raw.get("structured_data_keys", [])
    corporate_score = proxy.sub_scores.get("verifiable_corporate_identity")
    return [
        CoverageEntry(
            source_class="owned_site_metadata",
            status="found" if metadata else "missing",
            detail="Primary page metadata was checked." if metadata else "Primary page metadata could not be read.",
            confidence=proxy.confidence,
        ),
        CoverageEntry(
            source_class="structured_data",
            status="found" if structured_keys else "missing",
            detail=f"Structured data keys found: {', '.join(structured_keys)}" if structured_keys else "No structured data keys found.",
            confidence=proxy.confidence,
        ),
        CoverageEntry(
            source_class="corporate_registry",
            status="found" if (corporate_score or 0) > 50 else "missing",
            detail="Corporate identity evidence supplied." if (corporate_score or 0) > 50 else "No strong corporate registry evidence was available in this run.",
            confidence=proxy.confidence,
        ),
    ]


def _coverage_from_consistency(proxy: ProxyResult | None) -> list[CoverageEntry]:
    if proxy is None:
        return []
    raw = proxy.raw_data
    snapshots = raw.get("positioning_persistence", {}).get("snapshots", []) or raw.get("snapshots", [])
    wayback_error = raw.get("positioning_persistence", {}).get("error") or raw.get("wayback_error")
    llm_output = raw.get("positioning_persistence", {}).get("rationale") or raw.get("llm_output")
    return [
        CoverageEntry(
            source_class="historical_archive",
            status="found" if snapshots else "unavailable" if wayback_error else "missing",
            detail=f"{len(snapshots)} Wayback snapshots retrieved." if snapshots else f"Wayback unavailable: {wayback_error}" if wayback_error else "No historical snapshots found.",
            confidence=proxy.confidence,
        ),
        CoverageEntry(
            source_class="llm_consistency_judgment",
            status="found" if llm_output else "missing",
            detail="Structured model judgment completed." if llm_output else "Structured model judgment did not produce output.",
            confidence=proxy.confidence,
        ),
    ]


def _coverage_from_corroboration(proxy: ProxyResult | None) -> list[CoverageEntry]:
    if proxy is None:
        return []
    raw = proxy.raw_data
    claims = raw.get("cross_source_claim_consistency", {}).get("claims", []) or raw.get("claims", [])
    search_domains = raw.get("independent_mentions", {}).get("distinct_domains", []) or raw.get("search_domains", [])
    sampled_pages = raw.get("cross_source_claim_consistency", {}).get("sampled_pages", []) or raw.get("sampled_pages", [])
    return [
        CoverageEntry(
            source_class="owned_claim_surfaces",
            status="found" if sampled_pages else "missing",
            detail=f"{len(sampled_pages)} owned pages sampled." if sampled_pages else "No owned pages sampled.",
            confidence=proxy.confidence,
        ),
        CoverageEntry(
            source_class="owned_claim_extraction",
            status="found" if claims else "missing",
            detail=f"{len(claims)} auditable claims extracted." if claims else "No auditable claims extracted.",
            confidence=proxy.confidence,
        ),
        CoverageEntry(
            source_class="external_search_results",
            status="found" if search_domains else "missing",
            detail=f"External domains found: {', '.join(search_domains[:6])}" if search_domains else "External search did not surface relevant corroboration domains.",
            confidence=proxy.confidence,
        ),
    ]


def _coverage_from_authority(proxy: ProxyResult | None) -> list[CoverageEntry]:
    if proxy is None:
        return []
    raw = proxy.raw_data
    tier_1 = raw.get("tier_1_media_presence", {}).get("tier_1_hits", []) or raw.get("search_tier_1_hits", []) or raw.get("owned_tier_1_hits", [])
    tier_2 = raw.get("tier_2_media_presence", {}).get("tier_2_hits", []) or raw.get("search_tier_2_hits", []) or raw.get("owned_tier_2_hits", [])
    return [
        CoverageEntry(
            source_class="tier_1_authority_surfaces",
            status="found" if tier_1 else "missing",
            detail=f"Tier 1 hits: {', '.join(item.get('registered_domain', item.get('domain', '')) for item in tier_1[:6])}" if tier_1 else "No tier 1 authority hits found in this run.",
            confidence=proxy.confidence,
        ),
        CoverageEntry(
            source_class="tier_2_authority_surfaces",
            status="found" if tier_2 else "missing",
            detail=f"Tier 2 hits: {', '.join(item.get('registered_domain', item.get('domain', '')) for item in tier_2[:6])}" if tier_2 else "No tier 2 authority hits found in this run.",
            confidence=proxy.confidence,
        ),
    ]


def _coverage_from_behavioural(proxy: ProxyResult | None) -> list[CoverageEntry]:
    if proxy is None:
        return []
    raw = proxy.raw_data
    review_hits = len(raw.get("review_presence_and_consistency", {}).get("hits", [])) or raw.get("review_term_hits", 0)
    case_hits = len(raw.get("fulfillment_evidence", {}).get("candidate_pages", [])) or raw.get("case_study_term_hits", 0)
    return [
        CoverageEntry(
            source_class="review_surfaces",
            status="found" if review_hits else "missing",
            detail=f"{review_hits} review-related term hits on owned surface." if review_hits else "No strong review surface found in this run.",
            confidence=proxy.confidence,
        ),
        CoverageEntry(
            source_class="case_study_surfaces",
            status="found" if case_hits else "missing",
            detail=f"{case_hits} case-study-related term hits on owned surface." if case_hits else "No strong case-study surface found in this run.",
            confidence=proxy.confidence,
        ),
    ]
