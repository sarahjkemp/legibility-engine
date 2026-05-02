from __future__ import annotations

from statistics import mean

from .fetch import compact_terms, discover_internal_pages, fetch_page_snapshot, first_meaningful_sentence, infer_label
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
    channels: list[ChannelSurface] = []
    declared = _declared_surfaces(audit_input)
    website_snapshots: list[dict] = []
    existing_urls: set[str] = set()
    for key, label, role, platform, surface_type, url, source_text in declared:
        existing_urls.add(url)
        if source_text:
            cleaned = " ".join(source_text.split())
            message = first_meaningful_sentence(cleaned) or cleaned[:260]
            channels.append(
                ChannelSurface(
                    key=key,
                    label=label,
                    role=role,
                    platform=platform,
                    url=url,
                    surface_type=surface_type,
                    fetched=True,
                    blocked=False,
                    blocked_reason=None,
                    message=message,
                    raw_excerpt=cleaned[:1200],
                    title=None,
                    meta_description=None,
                    word_count=len(cleaned.split()),
                )
            )
            continue

        page = await fetch_page_snapshot(url, settings)
        if platform == "website":
            website_snapshots.append(page)
        blocked = not bool(page["text"])
        message = first_meaningful_sentence(page["excerpt"] or page["text"])
        if not message:
            reason = page.get("blocked_reason")
            message = reason or f"No usable content could be captured from this {infer_label(url).lower()} page."
        channels.append(
            ChannelSurface(
                key=key,
                label=label,
                role=role,
                platform=platform,
                url=url,
                surface_type=surface_type,
                fetched=bool(page["text"]),
                blocked=blocked,
                blocked_reason=page.get("blocked_reason"),
                message=message,
                raw_excerpt=(page["excerpt"] or page["text"][:500]) if page["text"] or page["excerpt"] else None,
                title=page["title"],
                meta_description=page["meta_description"],
                word_count=page["word_count"],
            )
        )

    discovered_pages = discover_internal_pages(
        str(audit_input.website_url),
        website_snapshots,
        existing_urls,
        settings.website_additional_page_limit,
    )
    for index, url in enumerate(discovered_pages, start=1):
        page = await fetch_page_snapshot(url, settings)
        website_snapshots.append(page)
        blocked = not bool(page["text"])
        message = first_meaningful_sentence(page["excerpt"] or page["text"])
        if not message:
            reason = page.get("blocked_reason")
            message = reason or "No usable content could be captured from this website page."
        label = page["title"] or f"Website Page {index}"
        channels.append(
            ChannelSurface(
                key=f"website_discovered_{index}",
                label=label,
                role="company",
                platform="website",
                url=url,
                surface_type="content",
                fetched=bool(page["text"]),
                blocked=blocked,
                blocked_reason=page.get("blocked_reason"),
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
    blocked_channels = [channel for channel in channels if channel.blocked]
    company_texts = [channel.message for channel in company_channels]
    spokesperson_texts = [channel.message for channel in spokesperson_channels]
    terms = compact_terms(company_texts + spokesperson_texts, audit_input.company_name)
    overlap = sum(1 for term in terms[:6] if any(term in text.lower() for text in spokesperson_texts)) if spokesperson_texts else 0

    website = next((channel for channel in channels if channel.platform == "website" and channel.key == "website"), None)
    company_content_count = len([channel for channel in company_channels if channel.surface_type == "content"])
    spokesperson_content_count = len([channel for channel in spokesperson_channels if channel.surface_type == "content"])
    usable_content_count = company_content_count + spokesperson_content_count
    website_score = _website_score(website)
    narrative = _narrative_score(
        company_channels,
        spokesperson_channels,
        terms,
        company_content_count,
        spokesperson_content_count,
        blocked_channels,
    )
    spokesperson = _spokesperson_score(spokesperson_channels, overlap, spokesperson_content_count, blocked_channels)
    overall = round(mean([narrative, website_score, spokesperson]), 1)

    website_phrase = _clean_phrase(website.message if website else None)
    company_profile = next((channel for channel in company_channels if channel.platform == "linkedin" and channel.surface_type == "profile"), None)
    spokesperson_best = next((channel for channel in spokesperson_channels if channel.surface_type == "content"), None)
    narrative_spine = [
        (
            f"The clearest owned-channel anchor is currently the website language: “{website_phrase}”."
            if website_phrase
            else "The website is currently the clearest owned source of truth in the captured material."
        ),
        (
            f"The company LinkedIn framing is currently: “{_clean_phrase(company_profile.message)}”."
            if company_profile
            else "Company profile-level messaging was thinner than the website narrative."
        ),
        (
            f"The strongest spokesperson narrative sample came from {spokesperson_best.label.lower()}: “{_clean_phrase(spokesperson_best.message)}”."
            if spokesperson_best
            else f"The spokesperson signal is weak because {audit_input.spokesperson_name or 'the spokesperson'} did not yield enough usable narrative-bearing content."
        ),
    ]
    where_the_story_breaks = [
        (
            f"The following supplied surfaces were not usable and should not be trusted in the current readout: {', '.join(channel.label for channel in blocked_channels[:4])}."
            if blocked_channels
            else "The main risk is not outright contradiction, but uneven repetition across channels."
        ),
        (
            f"The website leads with “{website_phrase}”, but that exact framing is not yet being repeated clearly enough across the other usable channels."
            if website_phrase
            else "The core offer is not yet being repeated in one clean, stable phrase across the usable channels."
        ),
        (
            f"{audit_input.spokesperson_name or 'The spokesperson'} is not yet acting as a fully reliable amplifier of the company story."
            if spokesperson < 7
            else f"{audit_input.spokesperson_name or 'The spokesperson'} is broadly aligned, but still needs to repeat the core company framing more explicitly."
        ),
    ]
    website_findings = _website_findings(website, company_channels)
    diagnosis = (
        "The business has a recognizable GEO narrative, but the strongest message is still concentrated on the website rather than being cleanly compounded across every declared surface."
    )
    retrieval_impact = (
        "AI systems form stronger, more stable memories of brands when the same audience, offer, and point of view appear repeatedly across the website, profile layers, and representative content. Right now the website is doing most of that work alone."
    )
    rationale = [
        f"{len(company_channels)} company-owned channels yielded usable content in this run.",
        (
            f"{len(spokesperson_channels)} spokesperson surfaces yielded usable content, giving a moderate alignment signal."
            if spokesperson_channels
            else "No spokesperson channel yielded strong text, so spokesperson alignment is provisional."
        ),
        (
            f"The website snapshot carried approximately {website.word_count} words of visible text."
            if website
            else "No website snapshot was available, limiting the GEO-readiness judgment."
        ),
        (
            f"{company_content_count + spokesperson_content_count} representative article/post/video URLs were captured, which gives a stronger read on actual messaging than profile pages alone."
            if company_content_count + spokesperson_content_count
            else "No representative article/post/video URLs were supplied, so the audit is still leaning more heavily on profile pages than ideal."
        ),
        (
            f"{len(blocked_channels)} supplied surfaces were rejected as unusable or platform boilerplate."
            if blocked_channels
            else "No supplied surfaces were rejected as platform boilerplate."
        ),
    ]
    what_to_fix_first = _action_items(audit_input, website, company_profile, spokesperson_best, blocked_channels, usable_content_count)
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
    company_content_count: int,
    spokesperson_content_count: int,
    blocked_channels: list[ChannelSurface],
) -> float:
    score = 3.6
    score += min(len(company_channels) * 0.6, 2.0)
    score += min(len(terms[:5]) * 0.35, 1.8)
    if spokesperson_channels:
        score += 0.8
    score += min(company_content_count * 0.35, 1.0)
    score += min(spokesperson_content_count * 0.25, 0.8)
    score -= min(len(blocked_channels) * 0.45, 2.5)
    if company_content_count + spokesperson_content_count < 3:
        score -= 1.0
    if any(term in {"youtube", "world", "posted"} for term in terms[:4]):
        score -= 1.2
    return min(round(score, 1), 10.0)


def _spokesperson_score(
    spokesperson_channels: list[ChannelSurface],
    overlap: int,
    spokesperson_content_count: int,
    blocked_channels: list[ChannelSurface],
) -> float:
    if not spokesperson_channels:
        return 3.0
    blocked_spokesperson = len([channel for channel in blocked_channels if channel.role == "spokesperson"])
    score = 4.0 + overlap + min(len(spokesperson_channels) * 0.5, 1.5) + min(spokesperson_content_count * 0.35, 1.0)
    score -= min(blocked_spokesperson * 0.5, 2.0)
    return min(round(score, 1), 10.0)


def _website_findings(website: ChannelSurface | None, company_channels: list[ChannelSurface]) -> list[str]:
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
    if not any(channel.surface_type == "content" and channel.platform == "website" for channel in company_channels):
        findings.append("The website currently carries the strategy language, but there are not yet enough additional website pages in the audit supplying named proof, outcomes, or examples.")
    return findings[:4]


def _value(url: object) -> str | None:
    return str(url) if url else None


def _clean_phrase(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split()).strip(" -")
    if len(cleaned) > 180:
        cleaned = cleaned[:177].rstrip() + "..."
    return cleaned


def _action_items(
    audit_input: AuditInput,
    website: ChannelSurface | None,
    company_profile: ChannelSurface | None,
    spokesperson_best: ChannelSurface | None,
    blocked_channels: list[ChannelSurface],
    usable_content_count: int,
) -> list[ActionItem]:
    website_phrase = _clean_phrase(website.message if website else None) or "the website’s core framing"
    items: list[ActionItem] = []

    if company_profile:
        company_phrase = _clean_phrase(company_profile.message) or "the current company profile wording"
        items.append(
            ActionItem(
                title="Align the company profile wording with the website anchor phrase",
                why_it_matters="Right now the website is carrying the clearest articulation of the business, while the company profile is using a different framing.",
                what_to_do=(
                    f"Keep the website line “{website_phrase}” as the source-of-truth version, then rewrite the company profile so it repeats that same audience/problem/offer more explicitly instead of relying on “{company_phrase}”."
                ),
            )
        )
    else:
        items.append(
            ActionItem(
                title="Make the company profile restate the homepage narrative",
                why_it_matters="If the profile layer is thinner or weaker than the website, AI systems form a less stable cross-channel memory of the business.",
                what_to_do=f"Lift the strongest website phrasing — “{website_phrase}” — into the company profile and make it the repeated line across profile descriptions.",
            )
        )

    if spokesperson_best:
        spokesperson_phrase = _clean_phrase(spokesperson_best.message) or "the current spokesperson content"
        items.append(
            ActionItem(
                title="Turn spokesperson content into a deliberate amplifier of the core narrative",
                why_it_matters="The spokesperson channels are where the brand can compound the message, not just vary it.",
                what_to_do=(
                    f"Use “{website_phrase}” as the anchor and rewrite recurring spokesperson intros/posts so they point back to that same core idea. Right now one of the clearer spokesperson samples is “{spokesperson_phrase}”, which should be made to connect more explicitly to the company offer."
                ),
            )
        )

    if blocked_channels:
        blocked_names = ", ".join(channel.label for channel in blocked_channels[:4])
        items.append(
            ActionItem(
                title="Replace unusable platform URLs with narrative-bearing links",
                why_it_matters="Several supplied URLs resolved to platform boilerplate rather than real brand messaging, which makes the audit weaker and the score less reliable.",
                what_to_do=(
                    f"Swap out {blocked_names} for exact article, post, or video URLs that contain the real message you want assessed. Generic profile or platform-shell URLs should not be trusted as strategic evidence."
                ),
            )
        )

    if usable_content_count < 3:
        items.append(
            ActionItem(
                title="Add more proof-bearing owned content before pushing authority outward",
                why_it_matters="The audit can see the narrative idea, but it still has too few narrative-bearing content surfaces and too little proof to make that idea feel fully grounded.",
                what_to_do="Add 2–3 concrete owned content pieces that restate the offer and show evidence: a named example, a clear point of view article, and a proof-led page or case-style write-up.",
            )
        )
    else:
        items.append(
            ActionItem(
                title="Build a tighter proof layer around the existing narrative",
                why_it_matters="The story is present, but it will convert into authority more effectively if each major claim is backed by visible examples or outcomes.",
                what_to_do="Take the strongest repeated narrative and add specific proof beside it: named client examples, visible outcomes, or a page that explains the methodology with evidence instead of just labels.",
            )
        )

    return items[:4]


def _declared_surfaces(audit_input: AuditInput) -> list[tuple[str, str, str, str, str, str, str | None]]:
    surfaces: list[tuple[str, str, str, str, str, str, str | None]] = []
    surfaces.append(("website", "Website", "company", "website", "website", str(audit_input.website_url), None))
    if audit_input.about_page_url:
        surfaces.append(("about_page", "About Page", "company", "website", "content", str(audit_input.about_page_url), None))

    surfaces.extend(
        _platform_surfaces(
            "company",
            "Company",
            "linkedin",
            audit_input.company_linkedin_url,
            audit_input.company_linkedin_post_urls,
            audit_input.company_linkedin_post_texts,
        )
    )
    surfaces.extend(
        _platform_surfaces(
            "company",
            "Company",
            "substack",
            audit_input.company_substack_url,
            audit_input.company_substack_article_urls,
            [],
        )
    )
    surfaces.extend(
        _platform_surfaces(
            "company",
            "Company",
            "medium",
            audit_input.company_medium_url,
            audit_input.company_medium_article_urls,
            audit_input.company_medium_article_texts,
        )
    )
    surfaces.extend(
        _platform_surfaces(
            "company",
            "Company",
            "youtube",
            audit_input.company_youtube_url,
            audit_input.company_youtube_video_urls,
            audit_input.company_youtube_video_texts,
        )
    )

    spokesperson = audit_input.spokesperson_name or "Spokesperson"
    surfaces.extend(
        _platform_surfaces(
            "spokesperson",
            spokesperson,
            "linkedin",
            audit_input.spokesperson_linkedin_url,
            audit_input.spokesperson_linkedin_post_urls,
            audit_input.spokesperson_linkedin_post_texts,
        )
    )
    surfaces.extend(
        _platform_surfaces(
            "spokesperson",
            spokesperson,
            "substack",
            audit_input.spokesperson_substack_url,
            audit_input.spokesperson_substack_article_urls,
            [],
        )
    )
    surfaces.extend(
        _platform_surfaces(
            "spokesperson",
            spokesperson,
            "medium",
            audit_input.spokesperson_medium_url,
            audit_input.spokesperson_medium_article_urls,
            audit_input.spokesperson_medium_article_texts,
        )
    )
    surfaces.extend(
        _platform_surfaces(
            "spokesperson",
            spokesperson,
            "youtube",
            audit_input.spokesperson_youtube_url,
            audit_input.spokesperson_youtube_video_urls,
            audit_input.spokesperson_youtube_video_texts,
        )
    )
    return surfaces


def _platform_surfaces(
    role: str,
    label_prefix: str,
    platform: str,
    profile_url: object,
    content_urls: list[object],
    content_texts: list[str],
) -> list[tuple[str, str, str, str, str, str, str | None]]:
    surfaces: list[tuple[str, str, str, str, str, str, str | None]] = []
    if profile_url:
        surfaces.append(
            (
                f"{role}_{platform}_profile",
                f"{label_prefix} {platform.title()} Profile",
                role,
                platform,
                "profile",
                str(profile_url),
                None,
            )
        )
    max_items = max(len(content_urls), len(content_texts))
    for index in range(1, min(max_items, 3) + 1):
        url = str(content_urls[index - 1]) if index - 1 < len(content_urls) else f"manual://{role}/{platform}/{index}"
        source_text = content_texts[index - 1] if index - 1 < len(content_texts) else None
        surfaces.append(
            (
                f"{role}_{platform}_content_{index}",
                f"{label_prefix} {platform.title()} Content {index}",
                role,
                platform,
                "content",
                url,
                source_text,
            )
        )
    return surfaces
