from __future__ import annotations

import asyncio

from .config import AuditConfig, EngineSettings, load_audit_config
from .coverage import build_coverage_summary
from .models import AuditResult, AuditTarget
from .proxies.behavioural import BehaviouralReliabilityProxy
from .proxies.consistency import ConsistencyProxy
from .proxies.provenance import ProvenanceProxy
from .scoring import build_score_summary


DEFAULT_PROXIES = [
    ProvenanceProxy(),
    ConsistencyProxy(),
    BehaviouralReliabilityProxy(),
]


async def run_audit(
    target: AuditTarget,
    config: AuditConfig | None = None,
    settings: EngineSettings | None = None,
) -> AuditResult:
    config = config or load_audit_config()
    settings = settings or EngineSettings()
    proxy_results = await asyncio.gather(
        *(proxy.run(target=target, config=config, settings=settings) for proxy in DEFAULT_PROXIES)
    )
    scores = build_score_summary(proxy_results, target.audit_type, config)
    coverage = build_coverage_summary(list(proxy_results))
    return AuditResult(
        target=target,
        scores=scores,
        source_coverage=coverage,
        proxy_results=list(proxy_results),
    )
