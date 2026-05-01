from __future__ import annotations

from statistics import mean

from ..collectors.site import fetch_page
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, Evidence, Finding, Observation, ProxyResult
from ..utils import format_exception


class BehaviouralReliabilityProxy:
    name = "behavioural_reliability"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        try:
            page = await fetch_page(str(target.primary_url), settings)
        except Exception as exc:
            return ProxyResult(
                proxy_name=self.name,
                findings=[
                    Finding(
                        severity="high",
                        headline="Behavioural collection failed",
                        detail=format_exception(exc),
                    )
                ],
            )

        text = page["text"].lower()
        case_study_terms = sum(term in text for term in ["case study", "client", "results", "outcome", "testimonial"])
        review_terms = sum(term in text for term in ["trustpilot", "g2", "reviews", "rating"])

        evidence = [
            Evidence(
                claim="Owned-surface fulfillment and review signals were checked in lite mode.",
                source_type="url",
                source=page["url"],
                excerpt=page["metadata"].get("meta_description"),
                confidence=0.55,
            )
        ]

        sub_scores = {
            "review_presence_and_consistency": min(100.0, review_terms * 20.0),
            "complaint_dispute_signals": 50.0,
            "fulfillment_evidence": min(100.0, case_study_terms * 18.0),
            "claim_to_evidence_ratio": min(100.0, (case_study_terms * 15.0) + (review_terms * 10.0)),
        }

        findings = [
            Finding(
                severity="medium",
                headline="Behavioural reliability is flags-first in v1",
                detail="This pass highlights evidence of reviews, outcomes, and case studies on the owned surface. External complaint and review systems should be added next.",
                evidence_refs=[evidence[0].id],
            )
        ]

        observations = [
            Observation(
                proxy=self.name,
                sub_component=key,
                metric="score",
                value=value,
                unit="points",
                source_refs=[evidence[0].id],
                method="computed",
                confidence=0.4,
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
            raw_data={"case_study_term_hits": case_study_terms, "review_term_hits": review_terms},
            confidence=0.4,
        )
