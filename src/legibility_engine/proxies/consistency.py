from __future__ import annotations

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, ProxyResult
from ..subscore_modules import (
    consistency_founder_voice,
    consistency_positioning_persistence,
    consistency_visual_identity,
    consistency_vocabulary_recurrence,
)
from ..subscores import build_proxy_result, failed_sub_score
from ..utils import format_exception


class ConsistencyProxy:
    name = "consistency"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        async def _safe(name: str, runner) -> object:
            try:
                return await runner
            except Exception as exc:
                return failed_sub_score(name, format_exception(exc))

        return build_proxy_result(
            self.name,
            {
                "positioning_persistence": await _safe("positioning_persistence", consistency_positioning_persistence.run(target, config, settings)),
                "vocabulary_recurrence": await _safe("vocabulary_recurrence", consistency_vocabulary_recurrence.run(target, config, settings)),
                "founder_key_voice_consistency": await _safe("founder_key_voice_consistency", consistency_founder_voice.run(target, config, settings)),
                "visual_identity_stability": await _safe("visual_identity_stability", consistency_visual_identity.run(target, config, settings)),
            },
        )
