from __future__ import annotations

from ..models import AuditResult


def render_markdown_worksheet(result: AuditResult) -> str:
    lines = [
        f"# {result.target.company_name} Legibility Audit",
        "",
        f"- Audit type: `{result.target.audit_type}`",
        f"- Primary URL: {result.target.primary_url}",
        f"- Composite score: `{result.scores.composite}`",
        f"- Benchmark: `{result.scores.benchmark}`",
        f"- Gap: `{result.scores.gap}`",
        "",
        "## Source Coverage",
        f"- Checked: `{result.source_coverage.checked}`",
        f"- Found: `{result.source_coverage.found}`",
        f"- Missing: `{result.source_coverage.missing}`",
        f"- Unavailable: `{result.source_coverage.unavailable}`",
        "",
        "### Coverage By Source Class",
    ]
    for entry in result.source_coverage.by_source_class:
        lines.append(
            f"- `{entry.source_class}`: `{entry.status}` ({entry.confidence}) — {entry.detail}"
        )

    lines.extend([
        "",
        "## Proxy Summary",
    ])
    for proxy_name, summary in result.scores.by_proxy.items():
        lines.append(
            f"- `{proxy_name}`: score `{summary.score}`, benchmark `{summary.benchmark}`, gap `{summary.gap}`, confidence `{summary.confidence}`"
        )

    for proxy in result.proxy_results:
        lines.extend(["", f"## {proxy.proxy_name}", ""])
        if proxy.findings:
            lines.append("### Findings")
            for finding in proxy.findings:
                lines.append(f"- [{finding.severity}] {finding.headline}: {finding.detail}")
        if proxy.sub_scores:
            lines.append("")
            lines.append("### Sub-scores")
            for key, value in proxy.sub_scores.items():
                lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"
