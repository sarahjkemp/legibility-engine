from __future__ import annotations

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, ProxyResult
from ..subscore_modules import (
    corroboration_citation_depth,
    corroboration_claim_consistency,
    corroboration_independent_mentions,
    corroboration_register_presence,
)
from ..subscores import build_proxy_result, failed_sub_score
from ..utils import format_exception


class CorroborationProxy:
    name = "corroboration"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        try:
            mentions = await corroboration_independent_mentions.run(target, config, settings)
        except Exception as exc:
            mentions = failed_sub_score("independent_mentions", format_exception(exc))
        filtered_results = mentions.raw_data.get("results", [])
        domains = mentions.raw_data.get("distinct_domains", [])
        try:
            claim_consistency = await corroboration_claim_consistency.run(target, config, settings, filtered_results)
        except Exception as exc:
            claim_consistency = failed_sub_score("cross_source_claim_consistency", format_exception(exc))
        try:
            citation_depth = await corroboration_citation_depth.run(target, config, settings, domains, filtered_results)
        except Exception as exc:
            citation_depth = failed_sub_score("citation_graph_depth", format_exception(exc))
        try:
            register_presence = await corroboration_register_presence.run(target, config, settings)
        except Exception as exc:
            register_presence = failed_sub_score("third_party_register_presence", format_exception(exc))
        return build_proxy_result(
            self.name,
            {
                "independent_mentions": mentions,
                "cross_source_claim_consistency": claim_consistency,
                "citation_graph_depth": citation_depth,
                "third_party_register_presence": register_presence,
            },
        )
