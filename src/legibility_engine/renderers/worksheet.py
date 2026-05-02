from __future__ import annotations

from ..geo_summary import build_geo_summary
from ..models import AuditResult


def render_markdown_worksheet(result: AuditResult) -> str:
    geo = build_geo_summary(result)
    lines = [
        f"# {result.target.company_name} GEO Narrative Audit",
        "",
        f"- Primary URL: {result.target.primary_url}",
        f"- Audit date: `{result.created_at.isoformat()}`",
        f"- Overall GEO Readiness: `{geo['overall_score']}` / 10",
        "",
        "## Declared Channels",
    ]

    for label, value in _declared_channels(result):
        if value:
            lines.append(f"- **{label}:** {value}")

    lines.extend(
        [
            "",
            "## Channel Messaging",
        ]
    )
    for item in geo["channel_snapshots"]:
        lines.append(f"- **{item['label']}:** {item['message']}")

    lines.extend(
        [
            "",
            "## Coverage",
            f"- Checked: `{result.source_coverage.checked}`",
            f"- Found: `{result.source_coverage.found}`",
            f"- Missing: `{result.source_coverage.missing}`",
            f"- Unavailable: `{result.source_coverage.unavailable}`",
            "",
            "## Narrative Coherence",
            f"- Score: `{geo['narrative_score']}` / 10",
        ]
    )
    lines.extend(_proxy_findings(result, "consistency"))
    lines.extend(["", "## Website GEO Readiness", f"- Score: `{geo['website_score']}` / 10"])
    lines.extend(_proxy_findings(result, "provenance"))
    lines.extend(["", "## Spokesperson Alignment", f"- Score: `{geo['spokesperson_score']}` / 10", f"- Diagnosis: {geo['diagnosis']}", f"- Rationale: {geo['rationale']}", f"- Best next move: {geo['next_step']}", "", "## Content Structure And Proof", f"- Score: `{geo['content_score']}` / 10"])
    lines.extend(_proxy_findings(result, "behavioural_reliability"))
    return "\n".join(lines) + "\n"


def _declared_channels(result: AuditResult) -> list[tuple[str, str | None]]:
    target = result.target
    return [
        ("Website", str(target.primary_url)),
        ("Company LinkedIn", _maybe_str(target.company_linkedin_url)),
        ("Company Substack", _maybe_str(target.company_substack_url)),
        ("Company Medium", _maybe_str(target.company_medium_url)),
        ("Company YouTube", _maybe_str(target.company_youtube_url)),
        ("Spokesperson", target.spokesperson_name or target.founder_name),
        ("Spokesperson LinkedIn", _maybe_str(target.spokesperson_linkedin_url or target.founder_linkedin_url)),
        ("Spokesperson Substack", _maybe_str(target.spokesperson_substack_url)),
        ("Spokesperson Medium", _maybe_str(target.spokesperson_medium_url)),
        ("Spokesperson YouTube", _maybe_str(target.spokesperson_youtube_url)),
    ]


def _proxy_findings(result: AuditResult, proxy_name: str) -> list[str]:
    proxy = next((item for item in result.proxy_results if item.proxy_name == proxy_name), None)
    if proxy is None:
        return ["- No data available for this section."]
    lines = []
    if proxy.findings:
        for finding in proxy.findings:
            lines.append(f"- [{finding.severity}] {finding.headline}: {finding.detail}")
    if not lines:
        lines.append("- No notable findings were surfaced for this section in the current run.")
    return lines


def _maybe_str(value: object) -> str | None:
    if value:
        return str(value)
    return None
