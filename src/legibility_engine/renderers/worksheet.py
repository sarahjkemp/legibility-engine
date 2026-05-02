from __future__ import annotations

from ..models import AuditResult


def render_markdown_worksheet(result: AuditResult) -> str:
    lines = [
        f"# {result.target.company_name} GEO Narrative Audit",
        "",
        f"- Primary URL: {result.target.primary_url}",
        f"- Audit date: `{result.created_at.isoformat()}`",
        "",
        "## Declared Channels",
    ]

    for label, value in _declared_channels(result):
        if value:
            lines.append(f"- **{label}:** {value}")

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
        ]
    )
    lines.extend(_proxy_section(result, "consistency"))
    lines.extend(["", "## Website GEO Readiness"])
    lines.extend(_proxy_section(result, "provenance"))
    lines.extend(["", "## Content Structure And Proof"])
    lines.extend(_proxy_section(result, "behavioural_reliability"))
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


def _proxy_section(result: AuditResult, proxy_name: str) -> list[str]:
    proxy = next((item for item in result.proxy_results if item.proxy_name == proxy_name), None)
    if proxy is None:
        return ["- No data available for this section."]
    lines = [f"- Score: `{proxy.score}`", f"- Confidence: `{proxy.confidence}`", ""]
    if proxy.findings:
        lines.append("### Findings")
        for finding in proxy.findings:
            lines.append(f"- [{finding.severity}] {finding.headline}: {finding.detail}")
    if proxy.sub_scores:
        lines.extend(["", "### Sub-scores"])
        for key, value in proxy.sub_scores.items():
            lines.append(f"- `{key}`: `{value}`")
    return lines


def _maybe_str(value: object) -> str | None:
    if value:
        return str(value)
    return None
