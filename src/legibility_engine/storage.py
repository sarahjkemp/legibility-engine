from __future__ import annotations

import json
from pathlib import Path

from .coverage import build_coverage_summary
from .models import AuditResult
from .renderers.worksheet import render_markdown_worksheet


def slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in cleaned.split("-") if part)
    return compact or "audit"


def save_audit_result(result: AuditResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(result.target.company_name)
    stem = f"{slug}-{result.audit_id[:8]}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_worksheet(result), encoding="utf-8")
    latest_json = output_dir / f"{slug}-latest.json"
    latest_md = output_dir / f"{slug}-latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    return {"json": json_path, "worksheet": md_path, "latest_json": latest_json, "latest_worksheet": latest_md}


def load_audit_result(path: Path) -> AuditResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    target = data.get("target", {})
    target.setdefault("sector", "other")
    target.setdefault("founder_linkedin_url", None)
    target.setdefault("founder_name", None)
    target.setdefault("official_substack_url", None)
    target.setdefault("official_medium_url", None)
    target.setdefault("official_youtube_url", None)
    target.setdefault("competitor_urls", [])
    data["target"] = target
    scores = data.get("scores", {})
    scores.setdefault("confidence", 0.0)
    data["scores"] = scores
    for proxy in data.get("proxy_results", []):
        proxy.setdefault("sub_score_results", {})
    if "source_coverage" not in data:
        partial = AuditResult.model_validate({**data, "source_coverage": {"checked": 0, "found": 0, "missing": 0, "unavailable": 0, "by_source_class": []}})
        coverage = build_coverage_summary(partial.proxy_results)
        data["source_coverage"] = coverage.model_dump(mode="json")
    return AuditResult.model_validate(data)


def list_audit_results(output_dir: Path) -> list[dict]:
    if not output_dir.exists():
        return []
    items = []
    for path in sorted(output_dir.glob("*.json"), reverse=True):
        if path.name.endswith("-latest.json"):
            continue
        try:
            result = load_audit_result(path)
        except Exception:
            continue
        items.append(
            {
                "audit_id": result.audit_id,
                "company_name": result.target.company_name,
                "audit_type": result.target.audit_type,
                "created_at": result.created_at.isoformat(),
                "composite": result.scores.composite,
                "gap": result.scores.gap,
                "json_path": str(path),
                "worksheet_path": str(path.with_suffix(".md")),
            }
        )
    return items


def find_audit_by_id(output_dir: Path, audit_id: str) -> AuditResult | None:
    for path in output_dir.glob("*.json"):
        if path.name.endswith("-latest.json"):
            continue
        try:
            result = load_audit_result(path)
        except Exception:
            continue
        if result.audit_id == audit_id:
            return result
    return None
