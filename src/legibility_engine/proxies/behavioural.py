from __future__ import annotations

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, ProxyResult
from ..subscore_modules import (
    behavioural_claim_evidence,
    behavioural_fulfillment,
)
from ..subscores import build_proxy_result, failed_sub_score
from ..utils import format_exception


class BehaviouralReliabilityProxy:
    name = "behavioural_reliability"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        async def _safe(name: str, runner) -> object:
            try:
                return await runner
            except Exception as exc:
                return failed_sub_score(name, format_exception(exc))

        return build_proxy_result(
            self.name,
            {
                "fulfillment_evidence": await _safe("fulfillment_evidence", behavioural_fulfillment.run(target, config, settings)),
                "claim_to_evidence_ratio": await _safe("claim_to_evidence_ratio", behavioural_claim_evidence.run(target, config, settings)),
            },
        )
