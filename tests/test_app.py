import asyncio

from legibility_engine.app import dashboard


def test_dashboard_uses_fresh_geo_audit_language() -> None:
    html = asyncio.run(dashboard())
    assert "Owned-channel GEO audit" in html
    assert "Channels To Audit" in html
    assert "Overall GEO Readiness" not in html
    assert "Legibility Engine" not in html
    assert "Competitor URLs" not in html
