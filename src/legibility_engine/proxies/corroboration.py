from __future__ import annotations

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, ProxyResult, SubScoreFinding, SubScoreResult
from ..subscore_modules import (
    corroboration_citation_depth,
    corroboration_claim_consistency,
    corroboration_independent_mentions,
    corroboration_register_presence,
)
from ..subscores import build_proxy_result
from ..utils import format_exception


class CorroborationProxy:
    name = "corroboration"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        try:
            mentions = await corroboration_independent_mentions.run(target, config, settings)
            filtered_results = mentions.raw_data.get("results", [])
            domains = mentions.raw_data.get("distinct_domains", [])
            claim_consistency = await corroboration_claim_consistency.run(target, config, settings, filtered_results)
            citation_depth = await corroboration_citation_depth.run(target, config, settings, domains, filtered_results)
            register_presence = await corroboration_register_presence.run(target, config, settings)
            return build_proxy_result(
                self.name,
                {
                    "independent_mentions": mentions,
                    "cross_source_claim_consistency": claim_consistency,
                    "citation_graph_depth": citation_depth,
                    "third_party_register_presence": register_presence,
                },
            )
        except Exception as exc:
            return build_proxy_result(
                self.name,
                {
                    "collection_failure": SubScoreResult(
                        score=None,
                        confidence=0.0,
                        findings=[SubScoreFinding(severity="high", text=f"Corroboration collection failed: {format_exception(exc)}")],
                        raw_data={"error": format_exception(exc)},
                    )
                },
            )
