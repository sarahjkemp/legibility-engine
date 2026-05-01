from __future__ import annotations

from statistics import mean
from urllib.parse import urlparse

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.search import count_distinct_domains, search_web
from ..collectors.site import fetch_internal_pages
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, Evidence, Finding, Observation, ProxyResult
from ..utils import format_exception


class CorroborationProxy:
    name = "corroboration"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        try:
            pages = await fetch_internal_pages(str(target.primary_url), settings, limit=3)
        except Exception as exc:
            return ProxyResult(
                proxy_name=self.name,
                findings=[
                    Finding(
                        severity="high",
                        headline="Corroboration collection failed",
                        detail=format_exception(exc),
                    )
                ],
            )

        root_domain = urlparse(str(target.primary_url)).netloc.replace("www.", "")
        page_urls = [page["url"] for page in pages]
        page_text = "\n\n".join(page["text"][:5000] for page in pages)
        external_domains = _collect_external_domains(pages, root_domain)
        supporting_domains = sorted(domain for domain in external_domains if domain not in config.owned_surface_domains)
        claim_payload = await _extract_claims(page_text, config, settings)
        claims = claim_payload.get("claims", [])
        repeated_terms = _collect_repeated_terms(page_text)
        proof_pages = [url for url in page_urls if any(term in url.lower() for term in ["case", "about", "work", "results", "proof"])]
        search_results = await _search_corroboration(target.company_name, str(target.primary_url), settings)
        excluded_domains = {root_domain, *config.owned_surface_domains}
        search_domains = count_distinct_domains(search_results, excluded_domains=excluded_domains)

        evidence = [
            Evidence(
                claim="Owned-surface pages were sampled to prepare corroboration checks.",
                source_type="url",
                source=page_urls[0],
                excerpt=", ".join(page_urls[:4]),
                confidence=0.72,
            )
        ]
        if claims:
            evidence.append(
                Evidence(
                    claim="Explicit claims were extracted from sampled owned content.",
                    source_type="llm_judgment" if settings.anthropic_api_key else "computation",
                    source="claim_extraction_v1",
                    excerpt=", ".join(claim["claim"] for claim in claims[:3]),
                    confidence=0.68,
                )
            )
        if supporting_domains:
            evidence.append(
                Evidence(
                    claim="Sampled owned content links to external domains that can support later verification.",
                    source_type="url",
                    source=page_urls[0],
                    excerpt=", ".join(supporting_domains[:8]),
                    confidence=0.6,
                )
            )
        if search_results:
            evidence.append(
                Evidence(
                    claim="External search results were sampled as an initial corroboration layer.",
                    source_type="url",
                    source=f"duckduckgo:{target.company_name}",
                    excerpt=", ".join(result["domain"] for result in search_results[:6]),
                    confidence=0.64,
                )
            )

        mention_score = min(100.0, 12.0 + (len(supporting_domains) * 4.0) + (len(search_domains) * 8.0))
        claim_consistency_score = min(100.0, 25.0 + (len(claims) * 4.0) + (len(repeated_terms) * 3.0) + (len(search_domains) * 3.0))
        citation_depth_score = min(100.0, (len(supporting_domains) * 4.0) + (len(proof_pages) * 8.0) + (len(search_domains) * 4.0))
        register_presence_score = 70.0 if target.companies_house_id else 25.0

        sub_scores = {
            "independent_mentions": round(mention_score, 2),
            "cross_source_claim_consistency": claim_consistency_score,
            "citation_graph_depth": round(citation_depth_score, 2),
            "third_party_register_presence": register_presence_score,
        }

        findings = []
        findings.append(
            Finding(
                severity="medium",
                headline="Corroboration is still operating in lite mode",
                detail=(
                    "This pass now extracts claims, samples external search results, and inspects proof structures "
                    "from owned content, but it still needs a stronger search/news source to reach full strength."
                ),
                evidence_refs=[item.id for item in evidence[:3]],
            )
        )
        if not claims:
            findings.append(
                Finding(
                    severity="medium",
                    headline="Few explicit auditable claims were found on sampled pages",
                    detail="The site may be conceptually clear without exposing many concrete claims that outside sources can corroborate.",
                    evidence_refs=[evidence[0].id],
                )
            )
        elif not supporting_domains and not search_domains:
            findings.append(
                Finding(
                    severity="medium",
                    headline="Owned content exposes claims but little external corroboration surfaced",
                    detail="That makes later corroboration harder for both agents and analysts.",
                    evidence_refs=[evidence[1].id],
                )
            )
        elif search_domains:
            findings.append(
                Finding(
                    severity="low",
                    headline="External search surfaced distinct corroboration candidates",
                    detail="The engine found multiple non-owned domains worth using for deeper claim verification in the next iteration.",
                    evidence_refs=[evidence[-1].id],
                )
            )

        observations = []
        for key, value in sub_scores.items():
            observations.append(
                Observation(
                    proxy=self.name,
                    sub_component=key,
                    metric="score",
                    value=value,
                    unit="points",
                    source_refs=[item.id for item in evidence],
                    method="computed",
                    confidence=0.52,
                )
            )
        for claim in claims[:8]:
            observations.append(
                Observation(
                    proxy=self.name,
                    sub_component="cross_source_claim_consistency",
                    metric="owned_claim",
                    value=claim["claim"],
                    source_refs=[evidence[1].id] if len(evidence) > 1 else [evidence[0].id],
                    method="llm_extract" if settings.anthropic_api_key else "computed",
                    confidence=0.62,
                )
            )

        return ProxyResult(
            proxy_name=self.name,
            score=round(mean(sub_scores.values()), 2),
            sub_scores=sub_scores,
            evidence=evidence,
            findings=findings,
            observations=observations,
            raw_data={
                "sampled_pages": page_urls,
                "distinct_external_domains": supporting_domains,
                "search_domains": search_domains,
                "search_results": search_results,
                "claims": claims,
                "repeated_terms": repeated_terms,
                "proof_pages": proof_pages,
            },
            confidence=0.6 if search_results else 0.54,
        )


async def _extract_claims(page_text: str, config: AuditConfig, settings: EngineSettings) -> dict:
    llm = AnthropicJSONClient(settings)
    if llm.available:
        try:
            payload = {"text": page_text[:12000]}
            result = await llm.run_prompt(config.prompt_dir / "claim_extraction_v1.md", payload)
            if isinstance(result, dict) and isinstance(result.get("claims"), list):
                return result
        except Exception:
            pass
    return {"claims": _heuristic_claims(page_text)}


def _heuristic_claims(text: str) -> list[dict]:
    claims = []
    sentences = [sentence.strip() for sentence in text.split(".") if sentence.strip()]
    markers = ["founded", "help", "built", "created", "works with", "used by", "%", "report", "audit"]
    for sentence in sentences:
        lowered = sentence.lower()
        if any(marker in lowered for marker in markers):
            claims.append(
                {
                    "claim": sentence[:180],
                    "claim_type": "other",
                    "supporting_excerpt": sentence[:220],
                }
            )
        if len(claims) >= 8:
            break
    return claims


def _collect_external_domains(pages: list[dict], root_domain: str) -> list[str]:
    domains = []
    for page in pages:
        for link in page["links"]:
            domain = urlparse(link).netloc.replace("www.", "")
            if domain and domain != root_domain:
                domains.append(domain)
    return sorted(set(domains))


def _collect_repeated_terms(text: str) -> list[str]:
    lowered = text.lower()
    candidates = ["legibility", "authority", "narrative", "proof", "signal", "ai", "brand"]
    return [term for term in candidates if lowered.count(term) >= 3]


async def _search_corroboration(company_name: str, primary_url: str, settings: EngineSettings) -> list[dict]:
    domain = urlparse(primary_url).netloc.replace("www.", "")
    domain_stem = domain.split(".")[0]
    queries = [
        f'"{company_name}" "{domain_stem}"',
        f'"{domain}"',
        f'"{company_name}" review',
    ]
    combined: list[dict] = []
    seen_urls: set[str] = set()
    for query in queries:
        try:
            results = await search_web(query, settings, limit=6)
        except Exception:
            continue
        for result in results:
            if result["url"] in seen_urls:
                continue
            if not _is_relevant_result(result, company_name, domain_stem):
                continue
            seen_urls.add(result["url"])
            combined.append(result)
    return combined[:10]


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
