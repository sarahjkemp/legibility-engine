from __future__ import annotations

from statistics import mean
from urllib.parse import urlparse

from ..collectors.search import count_distinct_domains, search_web
from ..collectors.site import fetch_page
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, Evidence, Finding, Observation, ProxyResult
from ..utils import format_exception


class AuthorityHierarchyProxy:
    name = "authority_hierarchy"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        try:
            page = await fetch_page(str(target.primary_url), settings)
        except Exception as exc:
            return ProxyResult(
                proxy_name=self.name,
                findings=[
                    Finding(
                        severity="high",
                        headline="Authority collection failed",
                        detail=format_exception(exc),
                    )
                ],
            )

        outbound_domains = {urlparse(link).netloc.replace("www.", "") for link in page["links"]}
        tier_1_hits = sorted(domain for domain in outbound_domains if domain in config.tier_1_domains)
        tier_2_hits = sorted(domain for domain in outbound_domains if domain in config.tier_2_domains)
        search_results = await _search_authority(target.company_name, str(target.primary_url), settings)
        search_domains = count_distinct_domains(search_results, excluded_domains={urlparse(str(target.primary_url)).netloc.replace("www.", "")})
        search_tier_1_hits = sorted(domain for domain in search_domains if domain in config.tier_1_domains)
        search_tier_2_hits = sorted(domain for domain in search_domains if domain in config.tier_2_domains)
        combined_tier_1 = sorted(set(tier_1_hits + search_tier_1_hits))
        combined_tier_2 = sorted(set(tier_2_hits + search_tier_2_hits))

        evidence = [
            Evidence(
                claim="Outbound references to known authority tiers were counted from the owned surface.",
                source_type="url",
                source=page["url"],
                excerpt=f"Tier 1: {', '.join(tier_1_hits) or 'none'} | Tier 2: {', '.join(tier_2_hits) or 'none'}",
                confidence=0.6,
            )
        ]
        if search_results:
            evidence.append(
                Evidence(
                    claim="External search results were sampled for authority-tier mentions.",
                    source_type="url",
                    source=f"duckduckgo:{target.company_name}",
                    excerpt=f"Tier 1: {', '.join(search_tier_1_hits) or 'none'} | Tier 2: {', '.join(search_tier_2_hits) or 'none'}",
                    confidence=0.64,
                )
            )

        sub_scores = {
            "tier_1_media_presence": min(100.0, len(combined_tier_1) * 25.0),
            "tier_2_media_presence": min(100.0, len(combined_tier_2) * 20.0),
            "podcast_conference_authority": 35.0,
            "professional_regulatory_body_recognition": 30.0 if not target.companies_house_id else 55.0,
            "inbound_citation_from_authoritative_sources": min(100.0, (len(combined_tier_1) * 20.0) + (len(combined_tier_2) * 10.0)),
        }

        findings = []
        if not combined_tier_1 and not combined_tier_2:
            findings.append(
                Finding(
                    severity="medium",
                    headline="No obvious authority-chain references surfaced yet",
                    detail="This does not prove the brand lacks authority, only that the current owned-surface and search sample did not expose much machine-legible authority evidence.",
                    evidence_refs=[evidence[0].id],
                )
            )
        elif search_tier_1_hits or search_tier_2_hits:
            findings.append(
                Finding(
                    severity="low",
                    headline="External search surfaced authority-tier candidates",
                    detail="The engine found non-owned domains in configured authority tiers that can be checked more deeply in the next iteration.",
                    evidence_refs=[evidence[-1].id],
                )
            )

        observations = [
            Observation(
                proxy=self.name,
                sub_component=key,
                metric="score",
                value=value,
                unit="points",
                source_refs=[evidence[0].id],
                method="computed",
                confidence=0.5 if search_results else 0.42,
            )
            for key, value in sub_scores.items()
        ]

        return ProxyResult(
            proxy_name=self.name,
            score=round(mean(sub_scores.values()), 2),
            sub_scores=sub_scores,
            evidence=evidence,
            findings=findings,
            observations=observations,
            raw_data={
                "owned_tier_1_hits": tier_1_hits,
                "owned_tier_2_hits": tier_2_hits,
                "search_tier_1_hits": search_tier_1_hits,
                "search_tier_2_hits": search_tier_2_hits,
                "search_results": search_results,
            },
            confidence=0.52 if search_results else 0.44,
        )


async def _search_authority(company_name: str, primary_url: str, settings: EngineSettings) -> list[dict]:
    domain = urlparse(primary_url).netloc.replace("www.", "")
    domain_stem = domain.split(".")[0]
    queries = [
        f'"{company_name}" "{domain_stem}" press',
        f'"{company_name}" "{domain_stem}" interview',
        f'"{company_name}" "{domain_stem}" conference',
    ]
    combined: list[dict] = []
    seen_urls: set[str] = set()
    for query in queries:
        try:
            results = await search_web(query, settings, limit=5)
        except Exception:
            continue
        for result in results:
            if result["url"] in seen_urls:
                continue
            if not _is_relevant_result(result, company_name, domain_stem):
                continue
            seen_urls.add(result["url"])
            combined.append(result)
    return combined[:12]


def _is_relevant_result(result: dict, company_name: str, domain_stem: str) -> bool:
    haystack = " ".join(
        [
            (result.get("title") or ""),
            (result.get("url") or ""),
            (result.get("snippet") or ""),
            (result.get("domain") or ""),
        ]
    ).lower()
    company_tokens = [token for token in company_name.lower().split() if len(token) > 2]
    if domain_stem.lower() in haystack:
        return True
    token_hits = sum(1 for token in company_tokens if token in haystack)
    return token_hits >= max(1, min(2, len(company_tokens)))
