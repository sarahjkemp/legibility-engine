from __future__ import annotations

import re

from .models import AuditResult, ProxyResult, SubScoreResult


def build_geo_summary(record: AuditResult) -> dict:
    consistency = _proxy(record, "consistency")
    provenance = _proxy(record, "provenance")
    behavioural = _proxy(record, "behavioural_reliability")
    spokesperson = _subscore(record, "consistency", "founder_key_voice_consistency")

    narrative = _to_ten(consistency.score if consistency else None)
    website = _to_ten(provenance.score if provenance else None)
    spokesperson_score = _to_ten(spokesperson.score if spokesperson else None)
    content = _to_ten(behavioural.score if behavioural else None)
    overall = _average([value for value in [narrative, website, spokesperson_score, content] if value is not None])

    return {
        "overall_score": overall,
        "narrative_score": narrative,
        "website_score": website,
        "spokesperson_score": spokesperson_score,
        "content_score": content,
        "channel_snapshots": _channel_snapshots(record),
        "diagnosis": _diagnosis(overall, narrative, website, spokesperson_score, content),
        "rationale": _rationale(record),
        "next_step": _next_step(narrative, website, spokesperson_score, content),
        "improvement_actions": _improvement_actions(narrative, website, spokesperson_score, content),
    }


def _proxy(record: AuditResult, name: str) -> ProxyResult | None:
    return next((proxy for proxy in record.proxy_results if proxy.proxy_name == name), None)


def _subscore(record: AuditResult, proxy_name: str, subscore_name: str) -> SubScoreResult | None:
    proxy = _proxy(record, proxy_name)
    if proxy is None:
        return None
    return proxy.sub_score_results.get(subscore_name)


def _to_ten(score: float | None) -> float | None:
    if score is None:
        return None
    return round(score / 10, 1)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _channel_snapshots(record: AuditResult) -> list[dict]:
    consistency = _proxy(record, "consistency")
    raw = consistency.raw_data if consistency else {}
    samples = raw.get("vocabulary_recurrence", {}).get("channel_snapshots") or raw.get("channel_snapshots") or []
    snapshots = []
    for item in samples:
        label = f"{item.get('role', '').title()} {item.get('platform', '').title()}".strip()
        if label.lower() == "company website":
            label = "Website"
        snapshots.append(
            {
                "label": label,
                "url": item.get("url", ""),
                "message": _clean_snapshot(item.get("excerpt", "")),
            }
        )
    if snapshots:
        return snapshots
    for label, url in _declared_channel_fallbacks(record):
        snapshots.append(
            {
                "label": label,
                "url": url,
                "message": "This channel was declared for the audit, but a usable messaging excerpt was not captured in the current run.",
            }
        )
    return snapshots


def _diagnosis(overall: float | None, narrative: float | None, website: float | None, spokesperson: float | None, content: float | None) -> str:
    if overall is None:
        return "This audit could not produce a reliable GEO diagnosis from the supplied channels."
    if narrative is not None and narrative < 4:
        return "The brand is unlikely to surface clearly in AI retrieval because the core narrative is fragmented across the declared channels."
    if website is not None and website < 5:
        return "The narrative exists, but the website is not yet structured clearly enough to act as a strong GEO source of truth."
    if spokesperson is not None and spokesperson < 5:
        return "The spokesperson is not reinforcing the same story strongly enough, which weakens retrieval consistency across surfaces."
    if content is not None and content < 5:
        return "The brand is saying the right kind of things in places, but the public content still lacks enough visible proof and structure to compound confidently."
    return "The brand has a usable GEO narrative base, but it still needs tighter repetition and structural discipline across channels to surface consistently."


def _rationale(record: AuditResult) -> str:
    consistency = _proxy(record, "consistency")
    provenance = _proxy(record, "provenance")
    parts = []
    if consistency and consistency.findings:
        parts.append(f"{consistency.findings[0].headline}. {consistency.findings[0].detail}")
    if provenance and provenance.findings:
        parts.append(f"{provenance.findings[0].headline}. {provenance.findings[0].detail}")
    return " ".join(parts[:2]) or "The current GEO readiness is based on the consistency of the declared channels and the structural clarity of the website."


def _next_step(narrative: float | None, website: float | None, spokesperson: float | None, content: float | None) -> str:
    weakest = min(
        [(label, score) for label, score in [
            ("narrative", narrative),
            ("website", website),
            ("spokesperson", spokesperson),
            ("content", content),
        ] if score is not None],
        key=lambda item: item[1],
        default=(None, None),
    )[0]
    if weakest == "narrative":
        return "Unify the core positioning and repeated language across the declared channels before doing any authority-building work."
    if weakest == "website":
        return "Tighten the website first so it becomes the clearest source of truth for GEO retrieval."
    if weakest == "spokesperson":
        return "Align the spokesperson surfaces to the company narrative so the same story is reinforced everywhere."
    if weakest == "content":
        return "Add clearer proof, named examples, and stronger claim support across the owned content before expanding outward."
    return "Standardize the core story across the owned channels, then use that stable narrative as the base for authority-building."


def _improvement_actions(narrative: float | None, website: float | None, spokesperson: float | None, content: float | None) -> list[dict]:
    actions: list[dict] = []
    if narrative is None or narrative < 7:
        actions.append(
            {
                "title": "Unify the core narrative across channels",
                "why": "AI systems surface brands more cleanly when the same positioning, audience, and offer are repeated across owned surfaces.",
                "impact": "This is the foundation move. Until the core narrative is consistent, authority-building will amplify confusion rather than clarity.",
            }
        )
    if website is None or website < 7:
        actions.append(
            {
                "title": "Make the website the clear GEO source of truth",
                "why": "The website is the strongest owned retrieval surface, so unclear structure, weak metadata, or thin attribution make the brand harder to restate accurately.",
                "impact": "Tightening website structure improves how reliably the brand can be summarized, quoted, and referenced by AI systems.",
            }
        )
    if spokesperson is None or spokesperson < 7:
        actions.append(
            {
                "title": "Align the spokesperson to the company story",
                "why": "When the founder or spokesperson describes the business differently from the website, AI retrieval gets mixed signals about what the company actually is.",
                "impact": "Bringing the spokesperson into alignment makes the narrative compound instead of splitting across surfaces.",
            }
        )
    if content is None or content < 7:
        actions.append(
            {
                "title": "Add stronger proof and evidence to the owned content",
                "why": "Claims are more retrievable and more credible when they are supported by named examples, outcomes, case studies, or other visible evidence.",
                "impact": "This gives the narrative more weight and makes later authority-building much easier to convert into trust.",
            }
        )
    actions.append(
        {
            "title": "Build authority only after the narrative is stable",
            "why": "Third-party coverage works best once the brand has one clear repeatable story to distribute across PR, partnerships, and external channels.",
            "impact": "This is the natural upsell path: narrative first, then authority building from a stable base.",
        }
    )
    return actions


def _clean_snapshot(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return "No clear messaging snapshot was captured from this channel."
    sentence = compact.split(". ")[0].strip()
    return sentence[:240]


def _declared_channel_fallbacks(record: AuditResult) -> list[tuple[str, str]]:
    target = record.target
    raw = [
        ("Website", str(target.primary_url)),
        ("Company LinkedIn", _maybe_str(target.company_linkedin_url)),
        ("Company Substack", _maybe_str(target.company_substack_url)),
        ("Company Medium", _maybe_str(target.company_medium_url)),
        ("Company YouTube", _maybe_str(target.company_youtube_url)),
        ("Spokesperson LinkedIn", _maybe_str(target.spokesperson_linkedin_url or target.founder_linkedin_url)),
        ("Spokesperson Substack", _maybe_str(target.spokesperson_substack_url)),
        ("Spokesperson Medium", _maybe_str(target.spokesperson_medium_url)),
        ("Spokesperson YouTube", _maybe_str(target.spokesperson_youtube_url)),
    ]
    return [(label, value) for label, value in raw if value]


def _maybe_str(value: object) -> str | None:
    if value:
        return str(value)
    return None
