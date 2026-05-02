from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from legibility_engine.models import (
    AuditResult,
    AuditTarget,
    CoverageSummary,
    Finding,
    ProxyResult,
    ProxyScoreSummary,
    ScoreSummary,
    SubScoreFinding,
    SubScoreResult,
)
from legibility_engine.report import render_report
from legibility_engine.storage import load_audit_result


def test_render_existing_sjk_labs_audit_to_html() -> None:
    record = _load_or_build_sjk_record()

    html = render_report(record, "html")

    assert "SJK Labs" in html
    assert "GEO Narrative Audit" in html
    assert "Declared Channels" in html
    assert "Channel Messaging" in html
    assert "Narrative Consistency" in html
    assert "Website GEO Readiness" in html
    assert "Spokesperson Alignment" in html
    assert "Content Structure And Proof" in html
    assert "Diagnosis" in html
    assert "Analyst recommendations to be added before client delivery" in html


def test_report_uses_owned_channel_language_not_old_proxy_chart_language() -> None:
    html = render_report(_build_record(), "html")
    assert "Declared Channels" in html
    assert "Proxy Benchmark Chart" not in html
    assert "Authority Hierarchy" not in html
    assert "Corroboration" not in html
    assert "/ 10" in html


def test_pdf_renders_non_empty_bytes() -> None:
    pdf = render_report(_build_record(), "pdf")
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000


def _load_or_build_sjk_record() -> AuditResult:
    audits_dir = Path(__file__).resolve().parents[1] / "audits"
    candidates = sorted(audits_dir.glob("sjk-labs*.json"), reverse=True)
    for candidate in candidates:
        try:
            return load_audit_result(candidate)
        except Exception:
            continue
    return _build_record(company_name="SJK Labs")


def _build_record(company_name: str = "Test Co") -> AuditResult:
    by_proxy = {
        "provenance": ProxyScoreSummary(score=64, benchmark=68, gap=4, confidence=0.82),
        "consistency": ProxyScoreSummary(score=66, benchmark=82, gap=16, confidence=0.62),
        "behavioural_reliability": ProxyScoreSummary(score=58, benchmark=68, gap=10, confidence=0.4),
    }
    proxy_results = [
        ProxyResult(
            proxy_name="provenance",
            score=64,
            confidence=0.82,
            findings=[Finding(severity="medium", headline="Metadata is mostly in place", detail="Core provenance signals are present, though authorship can still tighten.")],
        ),
        ProxyResult(
            proxy_name="consistency",
            score=66,
            confidence=0.62,
            findings=[Finding(severity="low", headline="Narrative coherence is evident", detail="The current owned surface shows a stable vocabulary and thesis.")],
            sub_score_results={
                "founder_key_voice_consistency": SubScoreResult(
                    score=75,
                    confidence=0.6,
                    findings=[SubScoreFinding(severity="low", text="The spokesperson is broadly aligned with the company narrative across the declared channels.")],
                )
            },
        ),
        ProxyResult(
            proxy_name="behavioural_reliability",
            score=58,
            confidence=0.4,
            findings=[Finding(severity="medium", headline="Public fulfilment proof is light", detail="Named case studies and visible proof remain limited on the declared surfaces.")],
        ),
    ]
    return AuditResult(
        audit_id="test-audit-id",
        created_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
        target=AuditTarget(
            company_name=company_name,
            primary_url="https://example.com",
            audit_type="founder_led",
            company_linkedin_url="https://www.linkedin.com/company/example/",
            spokesperson_name="Jane Example",
            spokesperson_linkedin_url="https://www.linkedin.com/in/jane-example/",
        ),
        scores=ScoreSummary(composite=63, benchmark=76, gap=13, by_proxy=by_proxy),
        source_coverage=CoverageSummary(checked=6, found=4, missing=2, unavailable=0, by_source_class=[]),
        proxy_results=proxy_results,
    )
