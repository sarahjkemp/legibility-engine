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
)
from legibility_engine.report import render_proxy_chart_svg, render_report
from legibility_engine.storage import load_audit_result


def test_render_existing_sjk_labs_audit_to_html() -> None:
    record = _load_or_build_sjk_record()

    html = render_report(record, "html")

    assert "SJK Labs" in html
    assert str(round(record.scores.composite or 0)) in html
    for proxy_name in [
        "Corroboration",
        "Provenance",
        "Consistency Over Time",
        "Authority Hierarchy",
        "Behavioural Reliability",
    ]:
        assert proxy_name in html
    assert "Analyst recommendations to be added before client delivery" in html


def test_gap_words_phrases_render_correctly() -> None:
    expectations = [
        (30, "significantly below"),
        (15, "below"),
        (5, "just below"),
        (-5, "at or near"),
        (-15, "above"),
    ]

    for gap, phrase in expectations:
        record = _build_record_with_gap(gap)
        html = render_report(record, "html")
        assert phrase in html


def test_chart_render_returns_svg_with_five_rect_bars() -> None:
    svg = render_proxy_chart_svg(_build_record_with_gap(12))
    assert svg.startswith("<svg")
    assert svg.count("<rect") == 5


def test_pdf_renders_non_empty_bytes() -> None:
    pdf = render_report(_build_record_with_gap(12), "pdf")
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
    return _build_record_with_gap(12, company_name="SJK Labs")


def _build_record_with_gap(gap: float, company_name: str = "Test Co") -> AuditResult:
    composite = 76 - gap
    by_proxy = {
        "corroboration": ProxyScoreSummary(score=48, benchmark=78, gap=30, confidence=0.8),
        "provenance": ProxyScoreSummary(score=64, benchmark=68, gap=4, confidence=0.82),
        "consistency": ProxyScoreSummary(score=66, benchmark=82, gap=16, confidence=0.62),
        "authority_hierarchy": ProxyScoreSummary(score=45, benchmark=76, gap=31, confidence=0.52),
        "behavioural_reliability": ProxyScoreSummary(score=58, benchmark=68, gap=10, confidence=0.4),
    }
    proxy_results = [
        ProxyResult(
            proxy_name="corroboration",
            score=48,
            confidence=0.8,
            findings=[Finding(severity="high", headline="External proof is thin", detail="Independent corroboration is sparse across visible third-party surfaces.")],
        ),
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
        ),
        ProxyResult(
            proxy_name="authority_hierarchy",
            score=45,
            confidence=0.52,
            findings=[Finding(severity="medium", headline="Authority chain is underdeveloped", detail="Tier-one and tier-two placements are not yet carrying enough trust into the brand.")],
        ),
        ProxyResult(
            proxy_name="behavioural_reliability",
            score=58,
            confidence=0.4,
            findings=[Finding(severity="medium", headline="Public fulfilment proof is light", detail="Named case studies and review density remain limited on the public surface.")],
        ),
    ]
    return AuditResult(
        audit_id="test-audit-id",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        target=AuditTarget(company_name=company_name, primary_url="https://example.com", audit_type="founder_led", companies_house_id="16300492"),
        scores=ScoreSummary(composite=composite, benchmark=76, gap=gap, by_proxy=by_proxy),
        source_coverage=CoverageSummary(checked=10, found=6, missing=4, unavailable=0, by_source_class=[]),
        proxy_results=proxy_results,
    )
