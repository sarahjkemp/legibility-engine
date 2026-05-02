from __future__ import annotations

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, ProxyResult, SubScoreFinding, SubScoreResult
from ..subscore_modules import (
    provenance_author_attribution,
    provenance_corporate_identity,
    provenance_domain_signals,
    provenance_publication_metadata,
    provenance_source_citation,
)
from ..subscores import build_proxy_result
from ..utils import format_exception


class ProvenanceProxy:
    name = "provenance"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        try:
            return build_proxy_result(
                self.name,
                {
                    "author_attribution": await provenance_author_attribution.run(target, config, settings),
                    "publication_metadata": await provenance_publication_metadata.run(target, config, settings),
                    "source_citation_in_content": await provenance_source_citation.run(target, config, settings),
                    "verifiable_corporate_identity": await provenance_corporate_identity.run(target, config, settings),
                    "domain_authority_signals": await provenance_domain_signals.run(target, config, settings),
                },
            )
        except Exception as exc:
            return build_proxy_result(
                self.name,
                {
                    "collection_failure": SubScoreResult(
                        score=None,
                        confidence=0.0,
                        findings=[SubScoreFinding(severity="high", text=f"Provenance collection failed: {format_exception(exc)}")],
                        raw_data={"error": format_exception(exc)},
                    )
                },
            )
