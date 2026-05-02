from __future__ import annotations

from statistics import mean

from .fetch import compact_terms, fetch_page_snapshot, first_meaningful_sentence, infer_label
from .llm import AuditLLM
from .models import ActionItem, AuditInput, AuditRecord, ChannelSurface, ScoreCard
from .settings import AppSettings


async def run_audit(audit_input: AuditInput, settings: AppSettings) -> AuditRecord:
    channels = await _collect_channels(audit_input, settings)
    analysis = await _analyze_channels(audit_input, channels, settings)
    scores = ScoreCard(
        overall_geo_readiness=analysis["overall_geo_readiness"],
        narrative_consistency=analysis["narrative_consistency"],
        website_geo_readiness=analysis["website_geo_readiness"],
        spokesperson_alignment=analysis["spokesperson_alignment"],
    )
    return AuditRecord(
        company_name=audit_input.company_name,
        inputs=audit_input,
        channels=analysis["channels"],
        scores=scores,
        diagnosis=analysis["diagnosis"],
        retrieval_impact=analysis["retrieval_impact"],
        narrative_spine=analysis["narrative_spine"],
        where_the_story_breaks=analysis["where_the_story_breaks"],
        website_findings=analysis["website_findings"],
        rationale=analysis["rationale"],
        what_to_fix_first=analysis["what_to_fix_first"],
    )


async def _collect_channels(audit_input: AuditInput, settings: AppSettings) -> list[ChannelSurface]:
    declared = [
        ("website", "Website", "company", "website", str(audit_input.website_url)),
        ("company_linkedin", "Company LinkedIn", "company", "linkedin", _value(audit_input.company_linkedin_url)),
        ("company_substack", "Company Substack", "company", "substack", _value(audit_input.company_substack_url)),
        ("company_medium", "Company Medium", "company", "medium", _value(audit_input.company_medium_url)),
        ("company_youtube", "Company YouTube", "company", "youtube", _value(audit_input.company_youtube_url)),
        (
            "spokesperson_linkedin",
            f"{audit_input.spokesperson_name or 'Spokesperson'} LinkedIn",
            "spokesperson",
            "linkedin",
            _value(audit_input.spokesperson_linkedin_url),
        ),
        (
            "spokesperson_substack",
            f"{audit_input.spokesperson_name or 'Spokesperson'} Substack",
            "spokesperson",
            "substack",
            _value(audit_input.spokesperson_substack_url),
        ),
        (
            "spokesperson_medium",
            f"{audit_input.spokesperson_name or 'Spokesperson'} Medium",
            "spokesperson",
            "medium",
            _value(audit_input.spokesperson_medium_url),
        ),
        (
            "spokesperson_youtube",
            f"{audit_input.spokesperson_name or 'Spokesperson'} YouTube",
            "spokesperson",
            "youtube",
            _value(audit_input.spokesperson_youtube_url),
        ),
    ]

    channels: list[ChannelSurface] = []
    for key, label, role, platform, url in declared:
        if not url:
            continue
        page = await fetch_page_snapshot(url, settings)
        blocked = not bool(page["text"])
        message = first_meaningful_sentence(page["excerpt"] or page["text"])
        if not message:
            message = f"No usable content could be captured from this {infer_label(url).lower()} page."
        channels.append(
            ChannelSurface(
                key=key,
                label=label,
                role=role,
                platform=platform,
                url=url,
                fetched=bool(page["text"]),
                blocked=blocked,
                message=message,
                raw_excerpt=(page["excerpt"] or page["text"][:500]) if page["text"] or page["excerpt"] else None,
                title=page["title"],
                meta_description=page["meta_description"],
                word_count=page["word_count"],
            )
        )
    return channels


async def _analyze_channels(
    audit_input: AuditInput,
    channels: list[ChannelSurface],
    settings: AppSettings,
) -> dict:
    llm = AuditLLM(settings)
    payload = {
        "company_name": audit_input.company_name,
        "spokesperson_name": audit_input.spokesperson_name,
        "channels": [
            {
                "key": channel.key,
                "label": channel.label,
                "role": channel.role,
                "platform": channel.platform,
                "message": channel.message,
                "raw_excerpt": channel.raw_excerpt,
                "title": channel.title,
                "meta_description": channel.meta_description,
                "word_count": channel.word_count,
            }
            for channel in channels
        ],
    }

    if llm.available:
        result = await llm.analyze(payload)
        if result:
            summary_map = {item["key"]: item["message"] for item in result.get("channel_summaries", [])}
            enriched = [
                channel.model_copy(update={"message": summary_map.get(channel.key, channel.message)})
                for channel in channels
            ]
            overall = round(
                mean(
                    [
                        float(result.get("narrative_consistency", 0)),
                        float(result.get("website_geo_readiness", 0)),
                        float(result.get("spokesperson_alignment", 0)),
                    ]
                ),
                1,
            )
            return {
                "channels": enriched,
                "overall_geo_readiness": overall,
                "narrative_consistency": float(result.get("narrative_consistency", 0)),
                "website_geo_readiness": float(result.get("website_geo_readiness", 0)),
                "spokesperson_alignment": float(result.get("spokesperson_alignment", 0)),
                "diagnosis": result.get("diagnosis", ""),
                "retrieval_impact": result.get("retrieval_impact", ""),
                "narrative_spine": list(result.get("narrative_spine", []))[:4],
                "where_the_story_breaks": list(result.get("where_the_story_breaks", []))[:4],
                "website_findings": list(result.get("website_findings", []))[:4],
                "rationale": list(result.get("rationale", []))[:4],
                "what_to_fix_first": [
                    ActionItem.model_validate(item) for item in list(result.get("what_to_fix_first", []))[:4]
                ],
            }

    return _fallback_analysis(audit_input, channels)


def _fallback_analysis(audit_input: AuditInput, channels: list[ChannelSurface]) -> dict:
    company_channels = [channel for channel in channels if channel.role == "company" and not channel.blocked]
    spokesperson_channels = [channel for channel in channels if channel.role == "spokesperson" and not channel.blocked]
    company_texts = [channel.message for channel in company_channels]
    spokesperson_texts = [channel.message for channel in spokesperson_channels]
    terms = compact_terms(company_texts + spokesperson_texts, audit_input.company_name)
    overlap = sum(1 for term in terms[:6] if any(term in text.lower() for text in spokesperson_texts)) if spokesperson_texts else 0

    website = next((channel for channel in channels if channel.platform == "website"), None)
    website_score = _website_score(website)
    narrative = _narrative_score(company_channels, spokesperson_channels, terms)
    spokesperson = _spokesperson_score(spokesperson_channels, overlap)
    overall = round(mean([narrative, website_score, spokesperson]), 1)

    narrative_spine = [
        f"The clearest repeated ideas across captured channels are: {', '.join(terms[:4]) or 'none repeated strongly enough yet'}.",
        "The website is currently the dominant source of truth in the captured material.",
        (
            f"{audit_input.spokesperson_name or 'The spokesperson'} reinforces part of the same story."
            if spokesperson_channels
            else "The spokesperson signal is weak because little or no spokesperson channel text was captured."
        ),
    ]
    where_the_story_breaks = [
        (
            "Several declared channels yielded no usable text, which means the brand is not repeating the story cleanly enough across all owned surfaces."
            if any(channel.blocked for channel in channels)
            else "The main risk is not contradiction, but uneven repetition across channels."
        ),
        (
            "The spokesperson is not yet acting as a fully reliable amplifier of the company story."
            if spokesperson < 7
            else "Spokesperson alignment is promising, but still needs more deliberate repetition of the core offer."
        ),
    ]
    website_findings = _website_findings(website)
    diagnosis = (
        "The business has the beginnings of a recognizable GEO narrative, but it is not yet repeated with enough consistency "
        "or structural clarity to make AI retrieval feel sharp and dependable."
    )
    retrieval_impact = (
        "AI systems form simpler, stronger memories of brands when the website and owned channels restate one clear proposition, "
        "for one audience, in recognizably similar language. Right now the signal is present, but not yet compounded."
    )
    rationale = [
        f"{len(company_channels)} company-owned channels yielded usable content in this run.",
        (
            f"{len(spokesperson_channels)} spokesperson channels yielded usable content, giving a moderate alignment signal."
            if spokesperson_channels
            else "No spokesperson channel yielded strong text, so spokesperson alignment is provisional."
        ),
        (
            f"The website snapshot carried approximately {website.word_count} words of visible text."
            if website
            else "No website snapshot was available, limiting the GEO-readiness judgment."
        ),
    ]
    what_to_fix_first = [
        ActionItem(
            title="Write one stable positioning sentence and repeat it everywhere",
            why_it_matters="AI retrieval improves when the same business description appears consistently across the website and owned channels.",
            what_to_do="Decide on one sentence for what the company does, who it helps, and why it is distinct. Use that sentence or a close variation across the homepage, About page, LinkedIn, and spokesperson bios.",
        ),
        ActionItem(
            title="Turn the website into the source of truth",
            why_it_matters="The website is the strongest owned surface for AI systems to quote, summarize, and trust.",
            what_to_do="Tighten the homepage and About page, make the offer explicit, add a clearer proof structure, and ensure the site states the same story as the channels around it.",
        ),
        ActionItem(
            title="Make the spokesperson reinforce the same narrative",
            why_it_matters="Founder and spokesperson channels often become the clearest public explanations of a business, especially in AI summaries.",
            what_to_do="Rewrite spokesperson bios, featured descriptions, and recurring channel intros so they reinforce the exact same audience, offer, and angle as the company site.",
        ),
        ActionItem(
            title="Add proof before building authority",
            why_it_matters="Authority-building converts much better when the owned narrative is already clear and supported by evidence.",
            what_to_do="Add named examples, outcomes, client proof, or sharper evidence on the owned surfaces first. Then build authority outward from a more stable story.",
        ),
    ]
    return {
        "channels": channels,
        "overall_geo_readiness": overall,
        "narrative_consistency": narrative,
        "website_geo_readiness": website_score,
        "spokesperson_alignment": spokesperson,
        "diagnosis": diagnosis,
        "retrieval_impact": retrieval_impact,
        "narrative_spine": narrative_spine,
        "where_the_story_breaks": where_the_story_breaks,
        "website_findings": website_findings,
        "rationale": rationale,
        "what_to_fix_first": what_to_fix_first,
    }


def _website_score(website: ChannelSurface | None) -> float:
    if website is None or website.blocked:
        return 2.5
    score = 3.5
    if website.title:
        score += 1.2
    if website.meta_description:
        score += 1.2
    if website.word_count >= 250:
        score += 1.1
    if website.raw_excerpt and any(token in website.raw_excerpt.lower() for token in ("about", "services", "work", "insights")):
        score += 0.8
    return min(round(score, 1), 10.0)


def _narrative_score(
    company_channels: list[ChannelSurface],
    spokesperson_channels: list[ChannelSurface],
    terms: list[str],
) -> float:
    score = 3.6
    score += min(len(company_channels) * 0.6, 2.0)
    score += min(len(terms[:5]) * 0.35, 1.8)
    if spokesperson_channels:
        score += 0.8
    return min(round(score, 1), 10.0)


def _spokesperson_score(spokesperson_channels: list[ChannelSurface], overlap: int) -> float:
    if not spokesperson_channels:
        return 3.0
    return min(round(4.0 + overlap + min(len(spokesperson_channels) * 0.5, 1.5), 1), 10.0)


def _website_findings(website: ChannelSurface | None) -> list[str]:
    if website is None or website.blocked:
        return ["The website could not be captured cleanly, so the site-level GEO judgment is limited."]
    findings = []
    if website.title:
        findings.append("The website exposes a usable page title, which helps AI systems summarize the business more accurately.")
    else:
        findings.append("The website lacks a clearly captured title signal, which weakens first-pass summarization.")
    if website.meta_description:
        findings.append("A meta description was present, giving the site a stronger retrieval summary layer.")
    else:
        findings.append("No strong meta description signal was captured, making the site's summary layer thinner than it should be.")
    if website.word_count < 180:
        findings.append("The visible website copy is still thin, which makes the business harder to interpret with confidence.")
    else:
        findings.append("The website has enough visible copy to communicate a point of view, but it still needs clearer proof and repetition.")
    return findings[:4]


def _value(url: object) -> str | None:
    return str(url) if url else None
