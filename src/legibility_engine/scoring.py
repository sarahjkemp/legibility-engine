from __future__ import annotations

from statistics import mean

from .config import AuditConfig
from .models import ProxyResult, ProxyScoreSummary, ScoreSummary


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


def build_score_summary(
    proxy_results: list[ProxyResult],
    audit_type: str,
    config: AuditConfig,
) -> ScoreSummary:
    audit_type_config = config.get_audit_type(audit_type)
    benchmark_config = config.get_benchmark(audit_type)
    by_proxy: dict[str, ProxyScoreSummary] = {}
    proxy_scores = {result.proxy_name: result.score for result in proxy_results}

    for proxy_name, benchmark in benchmark_config.proxies.items():
        result = next((item for item in proxy_results if item.proxy_name == proxy_name), None)
        score = result.score if result else None
        by_proxy[proxy_name] = ProxyScoreSummary(
            score=score,
            benchmark=benchmark,
            gap=round(benchmark - score, 2) if score is not None else None,
            confidence=result.confidence if result else 0.0,
        )

    composite = weighted_average(proxy_scores, audit_type_config.proxy_weights)
    benchmark = benchmark_config.composite
    return ScoreSummary(
        composite=composite,
        benchmark=benchmark,
        gap=round(benchmark - composite, 2) if composite is not None else None,
        by_proxy=by_proxy,
    )

