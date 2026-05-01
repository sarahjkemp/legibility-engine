from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditTarget(BaseModel):
    company_name: str
    primary_url: HttpUrl
    audit_type: str = "default"
    companies_house_id: str | None = None
    social_handles: dict[str, str] = Field(default_factory=dict)


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: f"e_{uuid4().hex[:10]}")
    claim: str
    source_type: Literal["url", "api", "computation", "llm_judgment", "system"]
    source: str
    excerpt: str | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    confidence: float = 1.0


class Finding(BaseModel):
    severity: Literal["low", "medium", "high"]
    headline: str
    detail: str
    evidence_refs: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    id: str = Field(default_factory=lambda: f"o_{uuid4().hex[:10]}")
    proxy: str
    sub_component: str
    metric: str
    value: Any
    unit: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    method: Literal["fetch", "parse", "llm_extract", "llm_judge", "computed"]
    confidence: float = 1.0
    observed_at: datetime = Field(default_factory=utcnow)


class ProxyResult(BaseModel):
    proxy_name: str
    score: float | None = None
    sub_scores: dict[str, float | None] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0


class ProxyScoreSummary(BaseModel):
    score: float | None
    benchmark: float
    gap: float | None
    confidence: float


class ScoreSummary(BaseModel):
    composite: float | None
    benchmark: float
    gap: float | None
    by_proxy: dict[str, ProxyScoreSummary]


class CoverageEntry(BaseModel):
    source_class: str
    status: Literal["checked", "found", "missing", "unavailable"]
    detail: str
    confidence: float = 0.0


class CoverageSummary(BaseModel):
    checked: int
    found: int
    missing: int
    unavailable: int
    by_source_class: list[CoverageEntry] = Field(default_factory=list)


class AuditResult(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=utcnow)
    engine_version: str = "0.1.0"
    target: AuditTarget
    scores: ScoreSummary
    source_coverage: CoverageSummary
    proxy_results: list[ProxyResult]
    analyst_notes: str | None = None
    report_status: str = "draft"
    client_visible_findings: list[Finding] = Field(default_factory=list)
