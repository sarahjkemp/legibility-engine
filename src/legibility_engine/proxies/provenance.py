from __future__ import annotations

from statistics import mean

from ..collectors.site import fetch_page
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, Evidence, Finding, Observation, ProxyResult
from ..utils import format_exception


class ProvenanceProxy:
    name = "provenance"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        try:
            page = await fetch_page(str(target.primary_url), settings)
        except Exception as exc:
            return ProxyResult(
                proxy_name=self.name,
                findings=[
                    Finding(
                        severity="high",
                        headline="Primary site fetch failed",
                        detail=format_exception(exc),
                    )
                ],
            )

        metadata = page["metadata"]
        structured_data = page.get("structured_data", {})
        evidence = [
            Evidence(
                claim="Primary site was successfully fetched for provenance checks.",
                source_type="url",
                source=page["url"],
                excerpt=metadata.get("title"),
                confidence=0.98,
            )
        ]
        observations: list[Observation] = []

        author_score = 100.0 if metadata.get("author") else 25.0
        publication_meta_score = 100.0 if metadata.get("article:published_time") else 40.0
        schema_present = bool(structured_data)
        schema_score = 100.0 if schema_present else 35.0
        https_score = 100.0 if str(target.primary_url).startswith("https://") else 0.0
        canonical_score = 100.0 if metadata.get("canonical_url") else 45.0
        corporate_identity_score = 30.0 if not target.companies_house_id else 75.0

        sub_scores = {
            "author_attribution": author_score,
            "publication_metadata": publication_meta_score,
            "source_citation_in_content": 50.0,
            "verifiable_corporate_identity": corporate_identity_score,
            "domain_authority_signals": round(mean([schema_score, https_score, canonical_score]), 2),
        }

        for key, value in sub_scores.items():
            observations.append(
                Observation(
                    proxy=self.name,
                    sub_component=key,
                    metric="score",
                    value=value,
                    unit="points",
                    source_refs=[evidence[0].id],
                    method="computed",
                    confidence=0.85,
                )
            )

        findings = []
        if not metadata.get("author"):
            findings.append(
                Finding(
                    severity="medium",
                    headline="No explicit author metadata found on primary page",
                    detail="Authorship is a useful provenance cue for both human analysts and AI systems.",
                    evidence_refs=[evidence[0].id],
                )
            )
        if not schema_present:
            findings.append(
                Finding(
                    severity="medium",
                    headline="Structured data is missing or unreadable",
                    detail="Schema markup strengthens machine-readable provenance and should be improved.",
                    evidence_refs=[evidence[0].id],
                )
            )

        score = round(mean(sub_scores.values()), 2)
        return ProxyResult(
            proxy_name=self.name,
            score=score,
            sub_scores=sub_scores,
            evidence=evidence,
            findings=findings,
            observations=observations,
            raw_data={"metadata": metadata, "structured_data_keys": list(structured_data.keys())},
            confidence=0.82,
        )
