from legibility_engine.models import AuditResult, AuditTarget, ProxyResult, ScoreSummary


def test_audit_result_model_can_render_minimal_payload() -> None:
    result = AuditResult(
        target=AuditTarget(company_name="Test Co", primary_url="https://example.com", audit_type="default"),
        scores=ScoreSummary(composite=50, benchmark=75, gap=25, by_proxy={}),
        proxy_results=[ProxyResult(proxy_name="provenance", score=50, confidence=0.7)],
    )

    payload = result.model_dump(mode="json")

    assert payload["target"]["company_name"] == "Test Co"
    assert payload["scores"]["gap"] == 25
