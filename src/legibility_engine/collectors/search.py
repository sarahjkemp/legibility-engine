from __future__ import annotations

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
        results.append({"title": title, "url": url, "domain": domain, "snippet": snippet, "source": "bing_api"})
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
            {"title": title, "url": link, "domain": domain, "snippet": description, "source": "bing_rss"}
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
        results.append({"title": title, "url": href, "domain": domain, "snippet": snippet, "source": "ddg_html"})
        if len(results) >= limit:
            break
    return results


def count_distinct_domains(results: list[dict], excluded_domains: set[str] | None = None) -> list[str]:
    excluded_domains = excluded_domains or set()
    domains = []
    for result in results:
        domain = (result.get("domain") or "").replace("www.", "")
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
    excluded = {owned_domain, *SOCIAL_DOMAINS, *(excluded_domains or set())}
    filtered = []
    for result in results:
        domain = (result.get("domain") or "").replace("www.", "")
        if not domain or domain in excluded or domain.endswith(f".{owned_domain}"):
            continue
        if sector != "b2b_saas" and domain in {"g2.com", "capterra.com"}:
            continue
        filtered.append(result)
    return filtered
