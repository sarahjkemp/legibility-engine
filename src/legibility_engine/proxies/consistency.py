from __future__ import annotations

from statistics import mean

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.site import fetch_page
from ..collectors.wayback import fetch_snapshots
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, Evidence, Finding, Observation, ProxyResult
from ..utils import format_exception


class ConsistencyProxy:
    name = "consistency"

    async def run(self, target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> ProxyResult:
        evidence: list[Evidence] = []
        findings: list[Finding] = []
        observations: list[Observation] = []

        try:
            current_page = await fetch_page(str(target.primary_url), settings)
        except Exception as exc:
            return ProxyResult(
                proxy_name=self.name,
                findings=[
                    Finding(
                        severity="high",
                        headline="Consistency collection failed",
                        detail=format_exception(exc),
                    )
                ],
            )

        snapshots: list[dict] = []
        wayback_error: Exception | None = None
        try:
            snapshots = await fetch_snapshots(str(target.primary_url), settings)
        except Exception as exc:
            wayback_error = exc

        evidence.append(
            Evidence(
                claim="Current and historical homepage surfaces were collected for consistency analysis.",
                source_type="url",
                source=str(target.primary_url),
                excerpt=current_page["metadata"].get("title"),
                confidence=0.9,
            )
        )
        for snapshot in snapshots:
            evidence.append(
                Evidence(
                    claim="Wayback snapshot retrieved.",
                    source_type="url",
                    source=snapshot["archive_url"],
                    excerpt=snapshot["timestamp"],
                    confidence=0.82,
                )
            )

        live_text = current_page["text"]
        live_title = (current_page["metadata"].get("title") or "").strip()
        recurring_terms = _extract_recurring_terms(live_text)
        founder_signal = _count_matches(live_text.lower(), ["sarah", "founder", "journalist", "sjk labs"])
        stable_identity_signal = _count_matches(live_text.lower(), ["legibility", "narrative", "authority", "ai"])

        sub_scores = {
            "positioning_persistence": 55.0 if snapshots else 48.0,
            "vocabulary_recurrence": min(100.0, 35.0 + (len(recurring_terms) * 8.0)),
            "founder_key_voice_consistency": min(100.0, 40.0 + (founder_signal * 10.0)),
            "visual_identity_stability": 60.0 if snapshots else min(100.0, 45.0 + (stable_identity_signal * 4.0)),
        }

        llm = AnthropicJSONClient(settings)
        llm_output = None
        if llm.available:
            payload = {
                "current_text_excerpt": current_page["text"][:6000],
                "snapshot_count": len(snapshots),
                "snapshots": snapshots,
                "current_page_title": live_title,
                "current_repeating_terms": recurring_terms,
            }
            try:
                llm_output = await llm.run_prompt(config.prompt_dir / "consistency_v1.md", payload)
            except Exception as exc:
                findings.append(
                    Finding(
                        severity="low",
                        headline="Structured LLM consistency pass failed",
                        detail=format_exception(exc),
                    )
                )

        if llm_output and isinstance(llm_output.get("positioning_persistence_score"), (int, float)):
            llm_positioning_score = float(llm_output["positioning_persistence_score"])
            if snapshots:
                sub_scores["positioning_persistence"] = llm_positioning_score
            vocab_items = llm_output.get("vocabulary_recurrence") or []
            if isinstance(vocab_items, list):
                frequency_sum = 0
                for item in vocab_items:
                    if isinstance(item, dict) and isinstance(item.get("frequency"), int | float):
                        frequency_sum += int(item["frequency"])
                if frequency_sum and snapshots:
                    sub_scores["vocabulary_recurrence"] = min(100.0, 40.0 + (frequency_sum * 5.0))
            findings.append(
                Finding(
                    severity="low",
                    headline="Consistency includes structured model judgment",
                    detail=_build_llm_finding_detail(llm_output, snapshots_present=bool(snapshots)),
                    evidence_refs=[evidence[0].id],
                )
            )

        if wayback_error:
            findings.append(
                Finding(
                    severity="medium",
                    headline="Wayback was unavailable, so consistency is provisional",
                    detail=(
                        "The proxy fell back to live-site signals only. "
                        f"Wayback error: {format_exception(wayback_error)}"
                    ),
                    evidence_refs=[evidence[0].id],
                )
            )

        for key, value in sub_scores.items():
            observations.append(
                Observation(
                    proxy=self.name,
                    sub_component=key,
                    metric="score",
                    value=value,
                    unit="points",
                    source_refs=[item.id for item in evidence[:2]] or [evidence[0].id],
                    method="computed",
                    confidence=0.7 if llm_output and snapshots else 0.6,
                )
            )

        score = round(mean(sub_scores.values()), 2)
        confidence = 0.78 if llm_output and snapshots else 0.62 if llm_output or not wayback_error else 0.52
        return ProxyResult(
            proxy_name=self.name,
            score=score,
            sub_scores=sub_scores,
            evidence=evidence,
            findings=findings,
            observations=observations,
            raw_data={
                "snapshots": snapshots,
                "llm_output": llm_output,
                "wayback_error": format_exception(wayback_error) if wayback_error else None,
                "recurring_terms": recurring_terms,
            },
            confidence=confidence,
        )


def _extract_recurring_terms(text: str, limit: int = 5) -> list[str]:
    lowered = text.lower()
    candidates = [
        "legibility",
        "authority",
        "narrative",
        "ai",
        "brand",
        "trust",
        "retrieval",
        "methodology",
        "visibility",
        "market",
    ]
    hits = [term for term in candidates if lowered.count(term) >= 2]
    return hits[:limit]


def _count_matches(text: str, needles: list[str]) -> int:
    return sum(1 for needle in needles if needle in text)


def _build_llm_finding_detail(llm_output: dict, snapshots_present: bool) -> str:
    rationale = llm_output.get("rationale", "Structured rationale unavailable.")
    if snapshots_present:
        return rationale
    return (
        "Structured model judgment ran successfully, but historical snapshots were unavailable, "
        "so numeric scoring stayed on the proxy's live-site fallback path. "
        f"Model rationale: {rationale}"
    )
