from __future__ import annotations

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, ProxyResult
from ..subscore_modules import (
    provenance_author_attribution,
    provenance_corporate_identity,
    provenance_domain_signals,
    provenance_publication_metadata,
    provenance_source_citation,
)
from ..subscores import build_proxy_result, failed_sub_score
from ..utils import format_exception


class ProvenanceProxy:
    name = "provenance"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        async def _safe(name: str, runner) -> object:
            try:
                return await runner
            except Exception as exc:
                return failed_sub_score(name, format_exception(exc))

        return build_proxy_result(
            self.name,
            {
                "author_attribution": await _safe("author_attribution", provenance_author_attribution.run(target, config, settings)),
                "publication_metadata": await _safe("publication_metadata", provenance_publication_metadata.run(target, config, settings)),
                "source_citation_in_content": await _safe("source_citation_in_content", provenance_source_citation.run(target, config, settings)),
                "verifiable_corporate_identity": await _safe("verifiable_corporate_identity", provenance_corporate_identity.run(target, config, settings)),
                "domain_authority_signals": await _safe("domain_authority_signals", provenance_domain_signals.run(target, config, settings)),
            },
        )
