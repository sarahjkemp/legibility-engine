from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from ..config import EngineSettings
from .transport import get_json, get_text

SOCIAL_DOMAINS = {
    "linkedin.com",
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
}


async def search_web(query: str, settings: EngineSettings, limit: int = 8) -> list[dict]:
    if settings.bing_search_api_key:
        try:
            results = await _search_bing_api(query, settings, limit=limit)
            if results:
                return results
        except Exception:
            pass

    try:
        results = await _search_bing_rss(query, settings, limit=limit)
        if results:
            return results
    except Exception:
        pass
    return await _search_duckduckgo_html(query, settings, limit=limit)


async def _search_bing_api(query: str, settings: EngineSettings, limit: int = 8) -> list[dict]:
    payload = await get_json(
        "https://api.bing.microsoft.com/v7.0/search",
        settings,
        params={"q": query, "count": limit, "responseFilter": "Webpages"},
        headers={"Ocp-Apim-Subscription-Key": settings.bing_search_api_key or ""},
        cache_namespace="bing_api_search",
    )
    values = (((payload or {}).get("webPages") or {}).get("value") or [])
    results: list[dict] = []
    for item in values:
        url = item.get("url")
        title = item.get("name")
        snippet = item.get("snippet") or ""
        if not url or not title:
            continue
        domain = urlparse(url).netloc.replace("www.", "")
        results.append(
            {
                "title": title,
                "url": url,
                "domain": domain,
                "registered_domain": get_registered_domain(domain),
                "snippet": snippet,
                "source": "bing_api",
            }
        )
        if len(results) >= limit:
            break
    return results


async def _search_bing_rss(query: str, settings: EngineSettings, limit: int = 8) -> list[dict]:
    text = await get_text(
        "https://www.bing.com/search",
        settings,
        params={"q": query, "format": "rss"},
        cache_namespace="bing_rss_search",
    )
    root = ElementTree.fromstring(text)
    results: list[dict] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        if not title or not link:
            continue
        domain = urlparse(link).netloc.replace("www.", "")
        results.append(
            {
                "title": title,
                "url": link,
                "domain": domain,
                "registered_domain": get_registered_domain(domain),
                "snippet": description,
                "source": "bing_rss",
            }
        )
        if len(results) >= limit:
            break
    return results


async def _search_duckduckgo_html(query: str, settings: EngineSettings, limit: int = 8) -> list[dict]:
    text = await get_text(
        f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
        settings,
        cache_namespace="ddg_html_search",
    )
    soup = BeautifulSoup(text, "html.parser")
    results: list[dict] = []
    for result in soup.select(".result"):
        anchor = result.select_one(".result__title a, a.result__a")
        if not anchor:
            continue
        href = anchor.get("href")
        title = anchor.get_text(" ", strip=True)
        snippet = ""
        snippet_node = result.select_one(".result__snippet")
        if snippet_node:
            snippet = snippet_node.get_text(" ", strip=True)
        if not href or not title:
            continue
        domain = urlparse(href).netloc.replace("www.", "")
        results.append(
            {
                "title": title,
                "url": href,
                "domain": domain,
                "registered_domain": get_registered_domain(domain),
                "snippet": snippet,
                "source": "ddg_html",
            }
        )
        if len(results) >= limit:
            break
    return results


def count_distinct_domains(results: list[dict], excluded_domains: set[str] | None = None) -> list[str]:
    excluded_domains = excluded_domains or set()
    domains = []
    for result in results:
        domain = get_registered_domain(result.get("registered_domain") or result.get("domain") or "")
        if domain and domain not in excluded_domains:
            domains.append(domain)
    return sorted(set(domains))


def filter_search_results(
    results: list[dict],
    *,
    owned_domain: str,
    excluded_domains: set[str] | None = None,
    sector: str | None = None,
) -> list[dict]:
    owned_registered = get_registered_domain(owned_domain)
    excluded = {owned_registered, *{get_registered_domain(domain) for domain in SOCIAL_DOMAINS}, *{get_registered_domain(domain) for domain in (excluded_domains or set())}}
    filtered = []
    for result in results:
        domain = get_registered_domain(result.get("registered_domain") or result.get("domain") or "")
        if not domain or domain in excluded or domain == owned_registered:
            continue
        if sector != "b2b_saas" and domain in {"g2.com", "capterra.com"}:
            continue
        filtered.append({**result, "registered_domain": domain})
    return filtered


def get_registered_domain(value: str) -> str:
    host = value.lower().strip()
    if "://" in host:
        host = urlparse(host).netloc
    host = host.replace("www.", "").split(":")[0]
    if not host:
        return ""
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return ".".join(parts)
    multi_part_suffixes = {
        "co.uk",
        "org.uk",
        "ac.uk",
        "gov.uk",
        "com.au",
        "net.au",
        "org.au",
        "co.nz",
        "com.br",
    }
    suffix = ".".join(parts[-2:])
    if suffix in multi_part_suffixes and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def normalize_brand_text(value: str) -> str:
    lowered = value.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def canonical_brand_pattern(brand_name: str) -> re.Pattern[str]:
    canonical = normalize_brand_text(brand_name)
    if not canonical:
        raise ValueError("Brand name cannot be empty after normalization")
    return re.compile(rf"(?<![a-z0-9]){re.escape(canonical)}(?![a-z0-9])")


def is_strict_brand_match(brand_name: str, text: str) -> bool:
    canonical_text = normalize_brand_text(text)
    if not canonical_text:
        return False
    return bool(canonical_brand_pattern(brand_name).search(canonical_text))


def filter_to_registered_domain_allowlist(results: list[dict], allowed_domains: set[str]) -> list[dict]:
    if not allowed_domains:
        raise ValueError("Allowed domain list cannot be empty")
    normalized_allowlist = {get_registered_domain(domain) for domain in allowed_domains}
    filtered = []
    for result in results:
        registered = get_registered_domain(result.get("registered_domain") or result.get("domain") or result.get("url") or "")
        if registered in normalized_allowlist:
            filtered.append({**result, "registered_domain": registered})
    return filtered


def dedupe_by_registered_domain(results: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for result in results:
        registered = get_registered_domain(result.get("registered_domain") or result.get("domain") or result.get("url") or "")
        if not registered or registered in seen:
            continue
        seen.add(registered)
        deduped.append({**result, "registered_domain": registered})
    return deduped


async def verify_brand_matches(results: list[dict], brand_name: str, settings: EngineSettings) -> list[dict]:
    verified = []
    for result in results:
        combined = " ".join([result.get("title") or "", result.get("snippet") or ""])
        if is_strict_brand_match(brand_name, combined):
            verified.append(result)
            continue
        try:
            page_text = await get_text(result["url"], settings, cache_namespace="search_result_page_text")
        except Exception:
            continue
        if is_strict_brand_match(brand_name, page_text):
            verified.append({**result, "matched_in_page": True})
    return verified
