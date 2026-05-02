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
