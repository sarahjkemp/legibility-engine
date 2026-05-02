from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

try:
    import extruct
except ImportError:  # pragma: no cover
    extruct = None

from ..config import EngineSettings
from .transport import get_text


async def fetch_page(url: str, settings: EngineSettings) -> dict:
    html = await get_text(url, settings, cache_namespace="site_pages")
    soup = BeautifulSoup(html, "html.parser")
    resolved_url = _resolved_canonical_url(url, soup) or url
    metadata = {
        "title": soup.title.string.strip() if soup.title and soup.title.string else None,
        "meta_description": _meta_content(soup, "description"),
        "canonical_url": _link_href(soup, "canonical"),
        "og:title": _meta_property(soup, "og:title"),
        "og:site_name": _meta_property(soup, "og:site_name"),
        "author": _meta_content(soup, "author"),
        "article:published_time": _meta_property(soup, "article:published_time"),
        "article:modified_time": _meta_property(soup, "article:modified_time"),
    }
    links = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not href:
            continue
        absolute = urljoin(resolved_url, href)
        if urlparse(absolute).scheme in {"http", "https"}:
            links.append(absolute)

    structured_data = {}
    if extruct is not None:
        try:
            structured_data = extruct.extract(html, base_url=resolved_url)
        except Exception:
            structured_data = {}

    return {
        "url": resolved_url,
        "status_code": 200,
        "html": html,
        "text": soup.get_text(" ", strip=True),
        "metadata": metadata,
        "links": links,
        "structured_data": structured_data,
    }


async def fetch_internal_pages(
    root_url: str,
    settings: EngineSettings,
    limit: int = 3,
) -> list[dict]:
    root_page = await fetch_page(root_url, settings)
    root_domain = urlparse(root_page["url"]).netloc.replace("www.", "")
    seen = {root_page["url"]}
    pages = [root_page]

    for link in root_page["links"]:
        if len(pages) >= limit + 1:
            break
        parsed = urlparse(link)
        domain = parsed.netloc.replace("www.", "")
        if domain != root_domain:
            continue
        if link in seen:
            continue
        if any(fragment in parsed.path.lower() for fragment in [".pdf", ".jpg", ".jpeg", ".png", ".svg"]):
            continue
        seen.add(link)
        try:
            pages.append(await fetch_page(link, settings))
        except Exception:
            continue
    return pages


def substantive_page_urls(pages: list[dict], limit: int = 20) -> list[str]:
    ranked: list[tuple[str, int]] = []
    for page in pages:
        text = page.get("text", "")
        score = len(text.split())
        if score < 120:
            continue
        ranked.append((page["url"], score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [url for url, _score in ranked[:limit]]


def _meta_content(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    return tag.get("content", "").strip() or None if tag else None


def _meta_property(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return tag.get("content", "").strip() or None if tag else None


def _link_href(soup: BeautifulSoup, rel: str) -> str | None:
    tag = soup.find("link", attrs={"rel": rel})
    return tag.get("href", "").strip() or None if tag else None


def _resolved_canonical_url(url: str, soup: BeautifulSoup) -> str | None:
    canonical = _link_href(soup, "canonical")
    if not canonical:
        return url
    return urljoin(url, canonical)
