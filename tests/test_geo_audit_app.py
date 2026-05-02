from fastapi.testclient import TestClient

from geo_narrative_audit.app import app


def test_dashboard_uses_geo_language() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "See the story your channels are actually telling." in html
    assert "Declare the channels" in html
    assert "Representative company content" in html
    assert "YouTube AI summaries or transcript excerpts" in html
    assert "does not rely on profile pages or post links anymore" in html
    assert "LinkedIn profile" not in html
    assert "One exact article URL per line" not in html
    assert "One exact video URL per line" not in html
    assert "Legibility Engine" not in html
    assert "Authority Hierarchy" not in html
