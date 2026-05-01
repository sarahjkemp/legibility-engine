from __future__ import annotations

from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from ..config import EngineSettings


async def search_web(query: str, settings: EngineSettings, limit: int = 8) -> list[dict]:
    rss_results = await _search_bing_rss(query, settings, limit=limit)
    if rss_results:
        return rss_results
    return await _search_duckduckgo_html(query, settings, limit=limit)


async def _search_bing_rss(query: str, settings: EngineSettings, limit: int = 8) -> list[dict]:
    headers = {"User-Agent": settings.user_agent}
    url = f"https://www.bing.com/search?q={quote_plus(query)}&format=rss"
    async with httpx.AsyncClient(timeout=settings.timeout_seconds, headers=headers, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    root = ElementTree.fromstring(response.text)
    results: list[dict] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        if not title or not link:
            continue
        domain = urlparse(link).netloc.replace("www.", "")
        results.append({"title": title, "url": link, "domain": domain, "snippet": description})
        if len(results) >= limit:
            break
    return results


async def _search_duckduckgo_html(query: str, settings: EngineSettings, limit: int = 8) -> list[dict]:
    headers = {"User-Agent": settings.user_agent}
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    async with httpx.AsyncClient(timeout=settings.timeout_seconds, headers=headers, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict] = []
    for anchor in soup.select(".result__title a, a.result__a"):
        href = anchor.get("href")
        title = anchor.get_text(" ", strip=True)
        if not href or not title:
            continue
        domain = urlparse(href).netloc.replace("www.", "")
        results.append({"title": title, "url": href, "domain": domain, "snippet": ""})
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
