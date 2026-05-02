from __future__ import annotations

from .models import Evidence, Finding, ProxyResult, SubScoreEvidence, SubScoreFinding, SubScoreResult
from .scoring import aggregate_proxy_score, proxy_confidence


def build_proxy_result(proxy_name: str, sub_score_results: dict[str, SubScoreResult]) -> ProxyResult:
    evidence: list[Evidence] = []
    findings: list[Finding] = []
    raw_data = {name: result.raw_data for name, result in sub_score_results.items()}

    for name, result in sub_score_results.items():
        evidence.extend(_convert_evidence(name, result.evidence))
        findings.extend(_convert_findings(name, result.findings))

    proxy = ProxyResult(
        proxy_name=proxy_name,
        sub_score_results=sub_score_results,
        evidence=evidence,
        findings=findings,
        raw_data=raw_data,
    )
    proxy.score = aggregate_proxy_score(proxy)
    proxy.confidence = proxy_confidence(proxy)
    return proxy


def _convert_evidence(sub_score_name: str, items: list[SubScoreEvidence]) -> list[Evidence]:
    return [
        Evidence(
            claim=sub_score_name.replace("_", " "),
            source_type="url" if item.source.startswith("http") else "api",
            source=item.source,
            excerpt=item.value,
        )
        for item in items
    ]


def _convert_findings(sub_score_name: str, items: list[SubScoreFinding]) -> list[Finding]:
    return [
        Finding(
            severity=item.severity,
            headline=sub_score_name.replace("_", " ").title(),
            detail=item.text,
        )
        for item in items
    ]


def failed_sub_score(name: str, message: str) -> SubScoreResult:
    return SubScoreResult(
        score=None,
        confidence=0.0,
        findings=[SubScoreFinding(severity="high", text=f"{name.replace('_', ' ').title()} failed: {message}")],
        raw_data={"error": message},
    )
