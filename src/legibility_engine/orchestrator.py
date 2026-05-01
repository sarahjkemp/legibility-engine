from __future__ import annotations

import asyncio

from .config import AuditConfig, EngineSettings, load_audit_config
from .models import AuditResult, AuditTarget
from .proxies.authority import AuthorityHierarchyProxy
from .proxies.behavioural import BehaviouralReliabilityProxy
from .proxies.consistency import ConsistencyProxy
from .proxies.corroboration import CorroborationProxy
from .proxies.provenance import ProvenanceProxy
from .scoring import build_score_summary


DEFAULT_PROXIES = [
    CorroborationProxy(),
    ProvenanceProxy(),
    ConsistencyProxy(),
    AuthorityHierarchyProxy(),
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
    return AuditResult(
        target=target,
        scores=scores,
        proxy_results=list(proxy_results),
    )

