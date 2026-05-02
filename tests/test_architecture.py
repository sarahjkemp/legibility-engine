from pathlib import Path

from legibility_engine.models import ProxyResult, SubScoreResult
from legibility_engine.scoring import build_score_summary, proxy_confidence
from legibility_engine.storage import load_audit_result


def test_proxy_confidence_uses_available_sub_scores() -> None:
    proxy = ProxyResult(
        proxy_name="corroboration",
        sub_score_results={
            "a": SubScoreResult(score=100),
            "b": SubScoreResult(score=None),
            "c": SubScoreResult(score=50),
            "d": SubScoreResult(score=None),
        },
    )

    assert proxy_confidence(proxy) == 0.5


def test_build_score_summary_ignores_null_sub_scores() -> None:
    from legibility_engine.config import load_audit_config

    config = load_audit_config()
    results = [
        ProxyResult(
            proxy_name="corroboration",
            sub_score_results={
                "independent_mentions": SubScoreResult(score=75),
                "cross_source_claim_consistency": SubScoreResult(score=None),
            },
        ),
        ProxyResult(proxy_name="provenance", score=70, confidence=0.8),
        ProxyResult(proxy_name="consistency", score=60, confidence=0.8),
        ProxyResult(proxy_name="authority_hierarchy", score=50, confidence=0.8),
        ProxyResult(proxy_name="behavioural_reliability", score=40, confidence=0.8),
    ]

    summary = build_score_summary(results, "default", config)

    assert summary.by_proxy["corroboration"].score == 75.0
    assert summary.by_proxy["corroboration"].confidence == 0.5
    assert summary.confidence > 0


def test_load_audit_result_backfills_new_target_fields(tmp_path: Path) -> None:
    path = tmp_path / "audit.json"
    path.write_text(
        """
        {
          "audit_id": "123",
          "created_at": "2026-05-01T10:00:00+00:00",
          "engine_version": "0.1.0",
          "target": {
            "company_name": "SJK Labs",
            "primary_url": "https://sjklabs.co",
            "audit_type": "founder_led",
            "companies_house_id": null,
            "social_handles": {}
          },
          "scores": {
            "composite": 44.2,
            "benchmark": 76,
            "gap": 31.8,
            "by_proxy": {}
          },
          "proxy_results": [],
          "analyst_notes": null,
          "report_status": "draft",
          "client_visible_findings": []
        }
        """,
        encoding="utf-8",
    )

    result = load_audit_result(path)

    assert result.target.sector == "other"
    assert result.target.founder_name is None
    assert result.target.company_linkedin_url is None
    assert result.target.company_substack_url is None
    assert result.target.company_medium_url is None
    assert result.target.company_youtube_url is None
    assert result.target.spokesperson_name is None
    assert result.target.spokesperson_linkedin_url is None
    assert result.target.spokesperson_substack_url is None
    assert result.target.spokesperson_medium_url is None
    assert result.target.spokesperson_youtube_url is None
    assert result.target.official_substack_url is None
    assert result.target.official_medium_url is None
    assert result.target.official_youtube_url is None
    assert result.target.competitor_urls == []
    assert result.scores.confidence == 0.0
