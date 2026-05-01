from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import AuditResult

AuditRecord = AuditResult

PROXY_ORDER = [
    "corroboration",
    "provenance",
    "consistency",
    "authority_hierarchy",
    "behavioural_reliability",
]

PROXY_LABELS = {
    "corroboration": "Corroboration",
    "provenance": "Provenance",
    "consistency": "Consistency Over Time",
    "authority_hierarchy": "Authority Hierarchy",
    "behavioural_reliability": "Behavioural Reliability",
}

PROXY_DEFINITIONS = {
    "corroboration": "How often, and how independently, the brand's claims are confirmed elsewhere.",
    "provenance": "Whether the brand's claims can be traced back to clear, verifiable sources.",
    "consistency": "Whether the brand has held a coherent thesis over time rather than drifting or pivoting.",
    "authority_hierarchy": "Whether trust flows to the brand from sources agents already treat as authoritative.",
    "behavioural_reliability": "Whether public evidence suggests the brand does what it says it does.",
}

REMEDIATION_PHRASES = {
    "corroboration": "increasing the volume and independence of external coverage and citation",
    "provenance": "tightening metadata, authorship, and verifiable identity signals on owned content",
    "consistency": "compounding existing narrative architecture rather than refreshing or repositioning it",
    "authority_hierarchy": "earning placement in tier-1 and tier-2 media and authoritative third-party sources",
    "behavioural_reliability": "surfacing fulfilment evidence, named case studies, and review density on public surfaces",
}

AUDIT_TYPE_LABELS = {
    "b2b_saas": "B2B SaaS / tech",
    "consumer_brand": "Consumer brand",
    "regulated": "Regulated",
    "founder_led": "Founder-led / personal brand",
    "default": "Default / unknown",
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "info": 3, "low": 4}


def render_report(record: AuditRecord, format: Literal["html", "pdf"]) -> str | bytes:
    context = _build_report_context(record)
    html = _template_env().get_template("client_report.html").render(**context)
    if format == "html":
        return html
    from weasyprint import HTML

    return HTML(string=html, base_url=str(_template_dir())).write_pdf()


def render_proxy_chart_svg(record: AuditRecord) -> str:
    rows = []
    x_label = 10
    x_bar = 235
    max_width = 420
    chart_height = 54 * len(PROXY_ORDER) + 24
    for index, proxy_name in enumerate(PROXY_ORDER):
        summary = record.scores.by_proxy.get(proxy_name)
        y = 18 + index * 54
        if summary is None:
            score = 0
            benchmark = 0
        else:
            score = summary.score or 0
            benchmark = summary.benchmark or 0
        benchmark_width = max_width * max(0, min(benchmark, 100)) / 100
        score_width = max_width * max(0, min(score, 100)) / 100
        rows.append(
            f'<text x="{x_label}" y="{y + 18}" font-size="18" fill="#1f3d2e" font-family="Inter, Arial, sans-serif">{escape(PROXY_LABELS[proxy_name])}</text>'
        )
        rows.append(
            f'<line x1="{x_bar}" y1="{y + 10}" x2="{x_bar + benchmark_width}" y2="{y + 10}" stroke="#1f3d2e" stroke-width="18" opacity="0.25" stroke-linecap="square"></line>'
        )
        rows.append(
            f'<rect x="{x_bar}" y="{y + 1}" width="{score_width}" height="18" fill="#1f3d2e"></rect>'
        )
        rows.append(
            f'<text x="{x_bar + max_width + 18}" y="{y + 18}" font-size="18" fill="#1f3d2e" font-family="Inter, Arial, sans-serif">{score:.0f}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{chart_height}" viewBox="0 0 760 {chart_height}" role="img" aria-label="Proxy scores chart">'
        + "".join(rows)
        + "</svg>"
    )


def _build_report_context(record: AuditRecord) -> dict:
    audit_type_human = AUDIT_TYPE_LABELS.get(record.target.audit_type, record.target.audit_type.replace("_", " ").title())
    top_gap_proxy = _top_gap_proxy(record)
    strongest_proxy = _strongest_proxy(record)
    top_gap_summary = record.scores.by_proxy[top_gap_proxy]
    strongest_summary = record.scores.by_proxy[strongest_proxy]
    gap = record.scores.gap or 0
    headline_summary = (
        f"{record.target.company_name} sits {_gap_words(gap)} the benchmark for {audit_type_human}. "
        f"The deficit is concentrated in {PROXY_LABELS[top_gap_proxy]}, which scores {fmt_num(top_gap_summary.score)} "
        f"against a benchmark of {fmt_num(top_gap_summary.benchmark)}. "
        f"{_strength_clause(record, strongest_proxy)} "
        f"The path to closing this gap runs through {REMEDIATION_PHRASES[top_gap_proxy]}."
    )
    return {
        "record": record,
        "company_name": record.target.company_name,
        "audit_type_human": audit_type_human,
        "report_date": _format_date(record.created_at),
        "headline_summary": headline_summary,
        "chart_svg": render_proxy_chart_svg(record),
        "top_gap_proxy_human": PROXY_LABELS[top_gap_proxy],
        "strongest_proxy_human": PROXY_LABELS[strongest_proxy],
        "three_frames": _build_three_frames(record, top_gap_proxy, strongest_proxy),
        "proxy_details": _build_proxy_details(record),
        "recommendations_placeholder": "[Analyst recommendations to be added before client delivery. This section is the human layer on top of the engine output, written based on the findings above and SJK Labs' strategic judgement.]",
    }


def _build_three_frames(record: AuditRecord, top_gap_proxy: str, strongest_proxy: str) -> dict:
    top_proxy_result = _get_proxy_result(record, top_gap_proxy)
    strongest_result = _get_proxy_result(record, strongest_proxy)
    gap_paragraphs = _findings_to_paragraphs(top_proxy_result, severities={"critical", "high", "medium"}, max_items=3)
    asset_paragraphs = _findings_to_paragraphs(strongest_result, severities={"critical", "high", "medium"}, max_items=3)
    if not asset_paragraphs:
        strongest_summary = record.scores.by_proxy[strongest_proxy]
        asset_paragraphs = [
            (
                f"The audit identified {PROXY_LABELS[strongest_proxy]} as the brand's strongest legibility signal, "
                f"scoring {fmt_num(strongest_summary.score)} against a benchmark of {fmt_num(strongest_summary.benchmark)}. "
                "This is the foundation the rest of the architecture should compound on."
            )
        ]
    info_candidates = []
    for proxy in record.proxy_results:
        info_candidates.extend(
            _paragraphs_from_findings(proxy.findings, severities={"info"}, max_items=10)
        )
    if not info_candidates:
        for proxy in record.proxy_results:
            if proxy.proxy_name in {top_gap_proxy, strongest_proxy}:
                continue
            info_candidates.extend(
                _paragraphs_from_findings(proxy.findings, severities={"medium"}, max_items=10)
            )
    return {
        "gap": gap_paragraphs,
        "asset": asset_paragraphs,
        "window": info_candidates[:3] or ["The current audit did not surface a distinct opportunity window beyond the core gap and strongest existing asset."],
    }


def _build_proxy_details(record: AuditRecord) -> list[dict]:
    details = []
    for proxy_name in PROXY_ORDER:
        proxy = _get_proxy_result(record, proxy_name)
        summary = record.scores.by_proxy.get(proxy_name)
        findings = _findings_to_paragraphs(proxy, severities={"critical", "high", "medium", "info", "low"}, max_items=10)
        details.append(
            {
                "name": PROXY_LABELS[proxy_name],
                "definition": PROXY_DEFINITIONS[proxy_name],
                "score_line": f"Score: {fmt_num(summary.score)} / Benchmark: {fmt_num(summary.benchmark)} / Gap: {fmt_num(summary.gap)}",
                "paragraphs": findings or ["No notable findings were surfaced for this proxy in the current audit run."],
                "confidence_sentence": _confidence_sentence(summary.confidence),
            }
        )
    return details


def _template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _template_dir() -> Path:
    return Path(__file__).parent / "templates"


def _format_date(value: datetime) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def _gap_words(gap: float) -> str:
    if gap > 20:
        return "significantly below"
    if gap > 10:
        return "below"
    if gap >= 0:
        return "just below"
    if gap >= -10:
        return "at or near"
    return "above"


def _strength_clause(record: AuditRecord, strongest_proxy: str) -> str:
    strongest_summary = record.scores.by_proxy[strongest_proxy]
    if strongest_summary.gap is not None and strongest_summary.gap <= 0:
        return f"By contrast, {PROXY_LABELS[strongest_proxy]} is at or above category expectation."
    return "No proxy currently sits at or above category expectation."


def _top_gap_proxy(record: AuditRecord) -> str:
    return max(
        PROXY_ORDER,
        key=lambda name: record.scores.by_proxy.get(name).gap if record.scores.by_proxy.get(name).gap is not None else float("-inf"),
    )


def _strongest_proxy(record: AuditRecord) -> str:
    return min(
        PROXY_ORDER,
        key=lambda name: record.scores.by_proxy.get(name).gap if record.scores.by_proxy.get(name).gap is not None else float("inf"),
    )


def _get_proxy_result(record: AuditRecord, proxy_name: str):
    return next(proxy for proxy in record.proxy_results if proxy.proxy_name == proxy_name)


def _findings_to_paragraphs(proxy, severities: set[str], max_items: int) -> list[str]:
    return _paragraphs_from_findings(proxy.findings, severities=severities, max_items=max_items)


def _paragraphs_from_findings(findings, severities: set[str], max_items: int) -> list[str]:
    filtered = [
        finding for finding in findings if finding.severity in severities
    ]
    filtered.sort(key=lambda finding: SEVERITY_ORDER.get(finding.severity, 99))
    paragraphs = []
    for finding in filtered[:max_items]:
        paragraphs.append(f"{finding.headline}. {finding.detail}")
    return paragraphs


def _confidence_sentence(confidence: float) -> str:
    if confidence >= 0.8:
        return "High confidence assessment."
    if confidence >= 0.5:
        return "Medium confidence — analyst review recommended."
    return "Lower confidence — this proxy benefits from additional manual review."


def fmt_num(value: float | None) -> str:
    if value is None:
        return "N/A"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"
