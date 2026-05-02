from __future__ import annotations

from collections import defaultdict

from ..collectors.anthropic_client import AnthropicJSONClient
from ..collectors.owned_channels import fetch_owned_channel_surfaces
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence, sampled_pages


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await sampled_pages(target, settings, limit=10)
    surfaces = [{"url": page["url"], "text": page["text"][:2500]} for page in pages[:6]]
    owned_surfaces = await fetch_owned_channel_surfaces(target, settings)
    for item in owned_surfaces:
        if item["platform"] == "website":
            continue
        surfaces.append({"url": item["url"], "text": item.get("text", "")[:2500]})
    llm = AnthropicJSONClient(settings)
    phrases: list[str] = []
    if llm.available:
        try:
            result = await llm.run_prompt(config.prompt_dir / "signature_phrases_v1.md", {"surfaces": surfaces})
            phrases = result.get("phrases", []) if isinstance(result, dict) else []
        except Exception:
            phrases = []
    if not phrases:
        phrases = ["legibility gap", "authority", "narrative strategy", "agent era", target.company_name.lower()]
    recurring = 0
    phrase_hits = {}
    for phrase in phrases[:5]:
        hits = sum(1 for surface in surfaces if phrase.lower() in surface["text"].lower())
        phrase_hits[phrase] = hits
        if hits >= 3:
            recurring += 1
    score = round((recurring / max(1, min(5, len(phrases[:5])))) * 100, 2)
    channel_snapshots = await _channel_snapshots(target, owned_surfaces, llm, config)
    return SubScoreResult(
        score=score,
        confidence=0.72 if phrases else 0.55,
        evidence=[evidence(surface["url"], surface["text"][:180]) for surface in surfaces[:6]],
        findings=[SubScoreFinding(severity="medium" if score < 50 else "low", text=f"{recurring} of the sampled signature phrases recurred across at least three surfaces.")],
        raw_data={
            "surfaces": [surface["url"] for surface in surfaces],
            "owned_channel_surfaces": [item["url"] for item in owned_surfaces],
            "channel_snapshots": channel_snapshots,
            "phrases": phrases,
            "phrase_hits": phrase_hits,
        },
    )


async def _channel_snapshots(
    target: AuditTarget,
    owned_surfaces: list[dict],
    llm: AnthropicJSONClient,
    config: AuditConfig,
) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in owned_surfaces:
        grouped[(item["role"], item["platform"])].append(item)

    channel_inputs = []
    for (role, platform), items in grouped.items():
        combined_text = "\n\n".join(
            (entry.get("snapshot") or entry.get("text") or "")[:700] for entry in items[:3]
        )
        label = _channel_label(role, platform)
        channel_inputs.append(
            {
                "key": f"{role}_{platform}",
                "role": role,
                "platform": platform,
                "label": label,
                "url": items[0]["url"],
                "text": combined_text[:2200],
            }
        )

    summaries: dict[str, str] = {}
    if llm.available and channel_inputs:
        try:
            result = await llm.run_prompt(
                config.prompt_dir / "channel_snapshots_v1.md",
                {
                    "company_name": target.company_name,
                    "channels": [
                        {"key": item["key"], "label": item["label"], "text": item["text"]}
                        for item in channel_inputs
                    ],
                },
            )
            if isinstance(result, dict):
                for item in result.get("channels", []):
                    key = item.get("key")
                    summary = item.get("summary")
                    if key and summary:
                        summaries[key] = summary.strip()
        except Exception:
            summaries = {}

    snapshots = []
    for item in channel_inputs:
        snapshots.append(
            {
                "role": item["role"],
                "platform": item["platform"],
                "label": item["label"],
                "url": item["url"],
                "excerpt": summaries.get(item["key"]) or _fallback_channel_summary(item["text"]),
            }
        )
    return snapshots


def _channel_label(role: str, platform: str) -> str:
    if role == "company" and platform == "website":
        return "Website"
    return f"{role.title()} {platform.title()}"


def _fallback_channel_summary(text: str) -> str:
    compact = " ".join(text.split()).strip()
    if not compact:
        return "This channel was declared for the audit, but a clear message could not be extracted from the current run."
    sentence = compact.split(". ")[0].strip()
    return sentence[:220]
