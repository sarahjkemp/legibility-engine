from __future__ import annotations

from typing import Protocol

from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, ProxyResult, SubScoreResult


class ProxyModule(Protocol):
    name: str

    async def run(
        self,
        target: AuditTarget,
        config: AuditConfig,
        settings: EngineSettings,
    ) -> ProxyResult:
        ...


class SubScoreModule(Protocol):
    name: str

    async def run(
        self,
        target: AuditTarget,
        config: AuditConfig,
        settings: EngineSettings,
    ) -> SubScoreResult:
        ...
