from __future__ import annotations

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, ProxyResult
from ..subscore_modules import (
    authority_bodies,
    authority_inbound_citation,
    authority_podcast_conference,
    authority_tier1,
    authority_tier2,
)
from ..subscores import build_proxy_result, failed_sub_score
from ..utils import format_exception


class AuthorityHierarchyProxy:
    name = "authority_hierarchy"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        async def _safe(name: str, runner) -> object:
            try:
                return await runner
            except Exception as exc:
                return failed_sub_score(name, format_exception(exc))

        tier_1 = await _safe("tier_1_media_presence", authority_tier1.run(target, config, settings))
        tier_2 = await _safe("tier_2_media_presence", authority_tier2.run(target, config, settings))
        authority_domains = [
            item.get("domain")
            for item in tier_1.raw_data.get("tier_1_hits", []) + tier_2.raw_data.get("tier_2_hits", [])
            if item.get("domain")
        ]
        return build_proxy_result(
            self.name,
            {
                "tier_1_media_presence": tier_1,
                "tier_2_media_presence": tier_2,
                "podcast_conference_authority": await _safe("podcast_conference_authority", authority_podcast_conference.run(target, config, settings)),
                "professional_regulatory_body_recognition": await _safe("professional_regulatory_body_recognition", authority_bodies.run(target, config, settings)),
                "inbound_citation_from_authoritative_sources": await _safe("inbound_citation_from_authoritative_sources", authority_inbound_citation.run(target, config, settings, authority_domains)),
            },
        )
