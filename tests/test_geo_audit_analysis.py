from geo_narrative_audit.analysis import _declared_surfaces, _fallback_analysis
from geo_narrative_audit.fetch import discover_internal_pages
from geo_narrative_audit.models import AuditInput, ChannelSurface


def test_fallback_analysis_returns_world_class_shape() -> None:
    audit_input = AuditInput(company_name="SJK Labs", website_url="https://sjklabs.co")
    channels = [
        ChannelSurface(
            key="website",
            label="Website",
            role="company",
            platform="website",
            url="https://sjklabs.co",
            surface_type="website",
            fetched=True,
            message="SJK Labs helps businesses strengthen narrative clarity and AI discoverability.",
            raw_excerpt="SJK Labs helps businesses strengthen narrative clarity and AI discoverability.",
            title="SJK Labs",
            meta_description="Narrative clarity and AI discoverability",
            word_count=220,
        ),
        ChannelSurface(
            key="spokesperson_linkedin",
            label="Sarah Kemp LinkedIn",
            role="spokesperson",
            platform="linkedin",
            url="https://linkedin.com/in/sarahjkemp",
            surface_type="content",
            fetched=True,
            message="Sarah Kemp writes about narrative architecture, authority building, and discoverability.",
            raw_excerpt="Sarah Kemp writes about narrative architecture, authority building, and discoverability.",
            word_count=120,
        ),
        ChannelSurface(
            key="company_youtube_content_1",
            label="Company Youtube Content 1",
            role="company",
            platform="youtube",
            url="https://youtube.com/watch?v=123",
            surface_type="content",
            fetched=False,
            blocked=True,
            blocked_reason="The supplied YouTube URL resolved to generic YouTube platform text rather than video-specific or channel-specific content.",
            message="The supplied YouTube URL resolved to generic YouTube platform text rather than video-specific or channel-specific content.",
            word_count=0,
        ),
    ]
    result = _fallback_analysis(audit_input, channels)
    assert 0 <= result["overall_geo_readiness"] <= 10
    assert 0 <= result["narrative_consistency"] <= 10
    assert 0 <= result["website_geo_readiness"] <= 10
    assert 0 <= result["spokesperson_alignment"] <= 10
    assert result["narrative_spine"]
    assert result["website_findings"]
    assert result["what_to_fix_first"]
    assert result["what_to_fix_first"][0].title
    assert "SJK Labs helps businesses strengthen narrative clarity and AI discoverability." in result["what_to_fix_first"][0].what_to_do
    assert result["narrative_consistency"] < 10


def test_declared_surfaces_prefers_pasted_platform_text() -> None:
    audit_input = AuditInput(
        company_name="SJK Labs",
        website_url="https://sjklabs.co",
        company_youtube_video_urls=["https://youtube.com/watch?v=123"],
        company_youtube_video_texts=["This video explains how SJK Labs approaches authority building for AI retrieval."],
    )
    surfaces = _declared_surfaces(audit_input)
    youtube_content = next(surface for surface in surfaces if surface[0] == "company_youtube_content_1")
    assert youtube_content[5] == "https://youtube.com/watch?v=123"
    assert youtube_content[6] == "This video explains how SJK Labs approaches authority building for AI retrieval."


def test_discover_internal_pages_prefers_high_signal_website_paths() -> None:
    snapshots = [
        {
            "internal_links": [
                "https://sjklabs.co/privacy-policy",
                "https://sjklabs.co/services",
                "https://sjklabs.co/insights",
                "https://sjklabs.co/methodology",
                "https://sjklabs.co/about",
            ]
        }
    ]
    discovered = discover_internal_pages(
        "https://sjklabs.co",
        snapshots,
        existing_urls={"https://sjklabs.co", "https://sjklabs.co/about"},
        limit=3,
    )
    assert "https://sjklabs.co/methodology" in discovered
    assert "https://sjklabs.co/services" in discovered
    assert "https://sjklabs.co/privacy-policy" not in discovered
