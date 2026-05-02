from geo_narrative_audit.analysis import _fallback_analysis
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
