from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import AuditResult, ProxyResult, SubScoreResult

AuditRecord = AuditResult

SECTION_TITLES = {
    "narrative_coherence": "Narrative Coherence",
    "website_readiness": "Website GEO Readiness",
    "spokesperson_alignment": "Spokesperson Alignment",
    "content_proof": "Content Structure And Proof",
}


def render_report(record: AuditRecord, format: Literal["html", "pdf"]) -> str | bytes:
    context = _build_report_context(record)
    html = _template_env().get_template("client_report.html").render(**context)
    if format == "html":
        return html
    from weasyprint import HTML

    return HTML(string=html, base_url=str(_template_dir())).write_pdf()


def _build_report_context(record: AuditRecord) -> dict:
    channels = _declared_channels(record)
    summary = _headline_summary(record, channels)
    sections = [
        {
            "title": "Narrative Coherence",
            "summary": _consistency_score_line(record),
            "paragraphs": _narrative_paragraphs(record),
        },
        {
            "title": "Website GEO Readiness",
            "summary": _website_score_line(record),
            "paragraphs": _website_paragraphs(record),
        },
        {
            "title": "Spokesperson Alignment",
            "summary": _spokesperson_score_line(record),
            "paragraphs": _spokesperson_paragraphs(record),
        },
        {
            "title": "Content Structure And Proof",
            "summary": _content_score_line(record),
            "paragraphs": _content_paragraphs(record),
        },
    ]
    return {
        "record": record,
        "company_name": record.target.company_name,
        "report_date": _format_date(record.created_at),
        "channels": channels,
        "headline_summary": summary,
        "coverage_summary": _coverage_summary(record),
        "sections": sections,
        "recommendations_placeholder": "[Analyst recommendations to be added before client delivery. This section is the human layer on top of the engine output, written based on the findings above and SJK Labs' strategic judgement.]",
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


def _headline_summary(record: AuditRecord, channels: list[dict]) -> str:
    supplied = len(channels)
    spokesperson_name = record.target.spokesperson_name or record.target.founder_name or "the spokesperson"
    has_spokesperson = any(item["role"] == "spokesperson" for item in channels)
    coverage_line = f"This audit analyzed {supplied} declared owned channels, centered on the website"
    if has_spokesperson:
        coverage_line += f" and {spokesperson_name}'s public surfaces"
    coverage_line += "."
    consistency = _find_proxy(record, "consistency")
    provenance = _find_proxy(record, "provenance")
    behavioural = _find_proxy(record, "behavioural_reliability")
    narrative = _first_finding_detail(consistency) or "Narrative consistency across channels is still being established."
    website = _first_finding_detail(provenance) or "The website remains the primary GEO surface and sets the baseline for retrieval clarity."
    proof = _first_finding_detail(behavioural) or "Public proof and structure on owned surfaces determine how confidently the story compounds."
    return f"{coverage_line} {narrative} {website} {proof}"


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


def _consistency_score_line(record: AuditRecord) -> str:
    proxy = _find_proxy(record, "consistency")
    return _simple_score_line(proxy, "Measures whether the same core story repeats clearly across the declared channels.")


def _website_score_line(record: AuditRecord) -> str:
    proxy = _find_proxy(record, "provenance")
    return _simple_score_line(proxy, "Measures how well the website communicates, structures, and attributes information for GEO retrieval.")


def _spokesperson_score_line(record: AuditRecord) -> str:
    subscore = _find_subscore(record, "consistency", "founder_key_voice_consistency")
    if subscore is None:
        return "Not yet assessed from a declared spokesperson surface."
    if subscore.score is None:
        return "Not yet assessed from a declared spokesperson surface."
    return f"Current alignment score: {subscore.score:.0f} / 100."


def _content_score_line(record: AuditRecord) -> str:
    proxy = _find_proxy(record, "behavioural_reliability")
    return _simple_score_line(proxy, "Measures whether the owned content includes visible proof, structure, and evidence to support its claims.")


def _simple_score_line(proxy: ProxyResult | None, definition: str) -> str:
    if proxy is None or proxy.score is None:
        return f"{definition} Current score not available."
    return f"{definition} Current score: {proxy.score:.0f} / 100."


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


def _first_finding_detail(proxy: ProxyResult | None) -> str | None:
    if proxy is None or not proxy.findings:
        return None
    first = proxy.findings[0]
    return f"{first.headline}. {first.detail}"


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
