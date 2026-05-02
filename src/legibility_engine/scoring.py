from __future__ import annotations

from statistics import mean

from .config import AuditConfig
from .models import ProxyResult, ProxyScoreSummary, ScoreSummary

COMPOSITE_CONFIDENCE_WEIGHTS = {
    "corroboration": 0.25,
    "provenance": 0.20,
    "consistency": 0.20,
    "authority_hierarchy": 0.20,
    "behavioural_reliability": 0.15,
}


def weighted_average(values: dict[str, float | None], weights: dict[str, float]) -> float | None:
    usable = [(key, value) for key, value in values.items() if value is not None and key in weights]
    if not usable:
        return None
    numerator = sum(value * weights[key] for key, value in usable)
    denominator = sum(weights[key] for key, _value in usable)
    if denominator == 0:
        return None
    return round(numerator / denominator, 2)


def average_confidence(results: list[ProxyResult]) -> float:
    if not results:
        return 0.0
    return round(mean(result.confidence for result in results), 2)


def sub_score_confidence(sub_scores: dict[str, float | None]) -> float:
    if not sub_scores:
        return 0.0
    with_data = sum(1 for value in sub_scores.values() if value is not None)
    return round(with_data / len(sub_scores), 2)


def aggregate_proxy_score(result: ProxyResult) -> float | None:
    if result.sub_score_results:
        values = [item.score for item in result.sub_score_results.values() if item.score is not None]
        return round(sum(values) / len(values), 2) if values else None
    if result.sub_scores:
        values = [item for item in result.sub_scores.values() if item is not None]
        return round(sum(values) / len(values), 2) if values else None
    return result.score


def proxy_confidence(result: ProxyResult) -> float:
    if result.sub_score_results:
        return sub_score_confidence({key: item.score for key, item in result.sub_score_results.items()})
    if result.sub_scores:
        return sub_score_confidence(result.sub_scores)
    return round(result.confidence, 2)


def composite_confidence(results: list[ProxyResult]) -> float:
    values = {result.proxy_name: proxy_confidence(result) for result in results}
    return weighted_average(values, COMPOSITE_CONFIDENCE_WEIGHTS) or 0.0


def build_score_summary(
    proxy_results: list[ProxyResult],
    audit_type: str,
    config: AuditConfig,
) -> ScoreSummary:
    audit_type_config = config.get_audit_type(audit_type)
    benchmark_config = config.get_benchmark(audit_type)
    by_proxy: dict[str, ProxyScoreSummary] = {}
    proxy_scores = {result.proxy_name: aggregate_proxy_score(result) for result in proxy_results}

    for proxy_name, benchmark in benchmark_config.proxies.items():
        result = next((item for item in proxy_results if item.proxy_name == proxy_name), None)
        score = aggregate_proxy_score(result) if result else None
        by_proxy[proxy_name] = ProxyScoreSummary(
            score=score,
            benchmark=benchmark,
            gap=round(benchmark - score, 2) if score is not None else None,
            confidence=proxy_confidence(result) if result else 0.0,
        )

    composite = weighted_average(proxy_scores, audit_type_config.proxy_weights)
    benchmark = benchmark_config.composite
    return ScoreSummary(
        composite=composite,
        benchmark=benchmark,
        gap=round(benchmark - composite, 2) if composite is not None else None,
        confidence=round(composite_confidence(proxy_results), 2),
        by_proxy=by_proxy,
    )
