from legibility_engine.config import load_audit_config
from legibility_engine.models import ProxyResult
from legibility_engine.scoring import build_score_summary


def test_build_score_summary_uses_config_weights() -> None:
    config = load_audit_config()
    results = [
        ProxyResult(proxy_name="corroboration", score=80, confidence=0.8),
        ProxyResult(proxy_name="provenance", score=70, confidence=0.8),
        ProxyResult(proxy_name="consistency", score=60, confidence=0.8),
        ProxyResult(proxy_name="authority_hierarchy", score=50, confidence=0.8),
        ProxyResult(proxy_name="behavioural_reliability", score=40, confidence=0.8),
    ]

    summary = build_score_summary(results, "default", config)

    assert summary.composite == 62.0
    assert summary.gap == 13.0
    assert summary.by_proxy["provenance"].gap == 2.0
