from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .geo_summary import build_geo_summary
from .models import AuditResult, ProxyResult, SubScoreResult

AuditRecord = AuditResult


def render_report(record: AuditRecord, format: Literal["html", "pdf"]) -> str | bytes:
    context = _build_report_context(record)
    html = _template_env().get_template("client_report.html").render(**context)
    if format == "html":
        return html
    from weasyprint import HTML

    return HTML(string=html, base_url=str(_template_dir())).write_pdf()


def _build_report_context(record: AuditRecord) -> dict:
    geo = build_geo_summary(record)
    channels = _declared_channels(record)
    sections = [
        {
            "title": "Channel Messaging",
            "summary": "What each declared channel is currently saying about the company.",
            "paragraphs": [
                f"On {item['label']}, the current messaging emphasizes: {item['message']}."
                for item in geo["channel_snapshots"]
            ] or ["No declared channel snapshots were captured beyond the website."],
        },
        {
            "title": "Narrative Consistency",
            "summary": _score_summary_line("Narrative consistency", geo["narrative_score"]),
            "paragraphs": _narrative_paragraphs(record),
        },
        {
            "title": "Website GEO Readiness",
            "summary": _score_summary_line("Website GEO readiness", geo["website_score"]),
            "paragraphs": _website_paragraphs(record),
        },
        {
            "title": "Spokesperson Alignment",
            "summary": _score_summary_line("Spokesperson alignment", geo["spokesperson_score"]),
            "paragraphs": _spokesperson_paragraphs(record),
        },
        {
            "title": "Content Structure And Proof",
            "summary": _score_summary_line("Content structure and proof", geo["content_score"]),
            "paragraphs": _content_paragraphs(record),
        },
        {
            "title": "Diagnosis",
            "summary": _score_summary_line("Overall GEO readiness", geo["overall_score"]),
            "paragraphs": [geo["diagnosis"], geo["rationale"], f"Best next move: {geo['next_step']}"],
        },
    ]
    return {
        "record": record,
        "company_name": record.target.company_name,
        "report_date": _format_date(record.created_at),
        "channels": channels,
        "headline_summary": geo["diagnosis"],
        "coverage_summary": _coverage_summary(record),
        "sections": sections,
        "improvement_actions": geo["improvement_actions"],
    }


def _declared_channels(record: AuditRecord) -> list[dict]:
    target = record.target
    raw = [
        ("Website", str(target.primary_url), "company"),
        ("Company LinkedIn", _maybe_str(target.company_linkedin_url), "company"),
        ("Company Substack", _maybe_str(target.company_substack_url), "company"),
        ("Company Medium", _maybe_str(target.company_medium_url), "company"),
        ("Company YouTube", _maybe_str(target.company_youtube_url), "company"),
        ("Spokesperson LinkedIn", _maybe_str(target.spokesperson_linkedin_url or target.founder_linkedin_url), "spokesperson"),
        ("Spokesperson Substack", _maybe_str(target.spokesperson_substack_url), "spokesperson"),
        ("Spokesperson Medium", _maybe_str(target.spokesperson_medium_url), "spokesperson"),
        ("Spokesperson YouTube", _maybe_str(target.spokesperson_youtube_url), "spokesperson"),
    ]
    return [{"label": label, "url": url, "role": role} for label, url, role in raw if url]


def _coverage_summary(record: AuditRecord) -> str:
    return (
        f"Coverage is based only on declared channels. "
        f"{record.source_coverage.found} source classes were found, "
        f"{record.source_coverage.missing} were missing, and "
        f"{record.source_coverage.unavailable} were unavailable."
    )


def _narrative_paragraphs(record: AuditRecord) -> list[str]:
    proxy = _find_proxy(record, "consistency")
    paragraphs = _proxy_findings(proxy)
    if not paragraphs:
        paragraphs = ["The current audit did not surface enough declared-channel material to form a strong narrative-consistency judgment."]
    return paragraphs


def _website_paragraphs(record: AuditRecord) -> list[str]:
    proxy = _find_proxy(record, "provenance")
    paragraphs = _proxy_findings(proxy)
    if not paragraphs:
        paragraphs = ["The website could not yet be assessed in enough depth to produce a strong GEO-readiness readout."]
    return paragraphs


def _spokesperson_paragraphs(record: AuditRecord) -> list[str]:
    subscore = _find_subscore(record, "consistency", "founder_key_voice_consistency")
    if subscore and subscore.findings:
        return [item.text for item in subscore.findings]
    if not (record.target.spokesperson_linkedin_url or record.target.founder_linkedin_url):
        return ["No spokesperson channel was supplied, so spokesperson alignment could not yet be assessed."]
    return ["A spokesperson channel was supplied, but the current run did not produce a full alignment reading."]


def _content_paragraphs(record: AuditRecord) -> list[str]:
    proxy = _find_proxy(record, "behavioural_reliability")
    paragraphs = _proxy_findings(proxy)
    if not paragraphs:
        paragraphs = ["The current audit did not surface enough owned-channel proof material to assess claim support cleanly."]
    return paragraphs


def _score_summary_line(label: str, score: float | None) -> str:
    if score is None:
        return f"{label.capitalize()} score not available from the current declared channels."
    return f"{label.capitalize()}: {score:.1f} / 10."


def _find_proxy(record: AuditRecord, name: str) -> ProxyResult | None:
    return next((proxy for proxy in record.proxy_results if proxy.proxy_name == name), None)


def _find_subscore(record: AuditRecord, proxy_name: str, subscore_name: str) -> SubScoreResult | None:
    proxy = _find_proxy(record, proxy_name)
    if proxy is None:
        return None
    return proxy.sub_score_results.get(subscore_name)


def _proxy_findings(proxy: ProxyResult | None) -> list[str]:
    if proxy is None:
        return []
    return [f"{item.headline}. {item.detail}" for item in proxy.findings]


def _template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _template_dir() -> Path:
    return Path(__file__).parent / "templates"


def _format_date(value: datetime) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def _maybe_str(value: object) -> str | None:
    if value:
        return str(value)
    return None
