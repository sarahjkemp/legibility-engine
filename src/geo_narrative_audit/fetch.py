from __future__ import annotations

import re
from urllib.parse import urljoin
from typing import Iterable
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .settings import AppSettings


async def fetch_page_snapshot(url: str, settings: AppSettings) -> dict:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.timeout_seconds,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception:
        return {
            "text": "",
            "excerpt": None,
            "title": None,
            "meta_description": None,
            "headings": [],
            "outbound_links": 0,
            "word_count": 0,
            "internal_links": [],
            "blocked_reason": "The page could not be fetched.",
        }

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    description = _meta_content(soup, "description")
    headings = [tag.get_text(" ", strip=True) for tag in soup.select("h1, h2")[:8]]
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    internal_host = urlparse(url).netloc.replace("www.", "")
    outbound_links = 0
    internal_links: list[str] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        absolute = urljoin(url, href)
        parsed = urlparse(absolute)
        if parsed.scheme in {"http", "https"}:
            host = parsed.netloc.replace("www.", "")
            if host and host != internal_host:
                outbound_links += 1
            elif host == internal_host:
                internal_links.append(_normalize_internal_url(absolute))
    excerpt = " ".join(part for part in [title, description, *headings[:2]] if part) or text[:900]
    blocked_reason = _blocked_reason(url, title, description, text)
    if blocked_reason:
        text = ""
        excerpt = None
    return {
        "text": text,
        "excerpt": excerpt[:1200] if excerpt else None,
        "title": title,
        "meta_description": description,
        "headings": headings,
        "outbound_links": outbound_links,
        "word_count": len(text.split()),
        "internal_links": list(dict.fromkeys(link for link in internal_links if link)),
        "blocked_reason": blocked_reason,
    }


def infer_label(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "linkedin.com" in host:
        return "LinkedIn"
    if "substack.com" in host:
        return "Substack"
    if "medium.com" in host:
        return "Medium"
    if "youtube.com" in host or "youtu.be" in host:
        return "YouTube"
    return "Website"


def first_meaningful_sentence(text: str | None) -> str | None:
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    for fragment in re.split(r"(?<=[.!?])\s+", normalized):
        sentence = fragment.strip()
        if 28 <= len(sentence) <= 320:
            return sentence
    return normalized[:220] if normalized else None


def compact_terms(texts: Iterable[str], company_name: str) -> list[str]:
    words: dict[str, int] = {}
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "your",
        "their",
        "into",
        "what",
        "when",
        "where",
        "have",
        "been",
        "will",
        "about",
        "they",
        "them",
        "more",
        "than",
        "just",
        "page",
        "website",
        "brand",
        "company",
        "youtube",
        "linkedin",
        "substack",
        "medium",
        "world",
        "posted",
        "topic",
        "enjoy",
        "videos",
        "music",
        "friends",
        "family",
        company_name.lower(),
    }
    for text in texts:
        for token in re.findall(r"[a-zA-Z][a-zA-Z\\-]{3,}", text.lower()):
            if token in stop:
                continue
            words[token] = words.get(token, 0) + 1
    return [token for token, _count in sorted(words.items(), key=lambda item: (-item[1], item[0]))[:10]]


def _meta_content(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    return tag.get("content", "").strip() or None if tag else None


def discover_internal_pages(
    website_url: str,
    snapshots: list[dict],
    existing_urls: set[str],
    limit: int,
) -> list[str]:
    if limit <= 0:
        return []

    homepage = _normalize_internal_url(website_url)
    candidates: dict[str, int] = {}
    for snapshot in snapshots:
        for link in snapshot.get("internal_links", []):
            normalized = _normalize_internal_url(link)
            if not normalized or normalized in existing_urls or normalized == homepage:
                continue
            if _is_ignorable_internal_path(normalized):
                continue
            candidates[normalized] = max(candidates.get(normalized, -999), _score_internal_path(normalized))

    ranked = sorted(candidates.items(), key=lambda item: (-item[1], item[0]))
    return [url for url, _score in ranked[:limit]]


def _blocked_reason(url: str, title: str | None, description: str | None, text: str) -> str | None:
    host = urlparse(url).netloc.lower()
    combined = " ".join(part for part in [title or "", description or "", text[:1200]] if part).lower()

    if "youtube.com" in host or "youtu.be" in host:
        if "enjoy the videos and music you love" in combined or "share it all with friends, family, and the world on youtube" in combined:
            return "The supplied YouTube URL resolved to generic YouTube platform text rather than video-specific or channel-specific content."
    if "linkedin.com" in host:
        if "linkedin: log in or sign up" in combined or "sign in" in combined and "join now" in combined:
            return "The supplied LinkedIn URL returned login or platform chrome rather than the post/profile text itself."
    if "medium.com" in host:
        if "discover stories, thinking, and expertise" in combined or "medium – where good ideas find you" in combined:
            return "The supplied Medium URL resolved to generic Medium platform copy rather than article-specific text."
    if "substack.com" in host:
        if "discover more from" in combined and "subscribe now" in combined and len(combined) < 500:
            return "The supplied Substack URL returned mostly subscription chrome rather than enough article or publication text to assess."
    return None


def _normalize_internal_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    normalized_path = re.sub(r"/{2,}", "/", path).rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc.lower()}{normalized_path}"


def _score_internal_path(url: str) -> int:
    path = urlparse(url).path.lower()
    score = 0
    preferred_tokens = {
        "about": 8,
        "services": 8,
        "service": 7,
        "work": 7,
        "case-study": 9,
        "case-studies": 9,
        "results": 7,
        "insights": 7,
        "blog": 6,
        "method": 8,
        "methodology": 9,
        "approach": 8,
        "framework": 8,
        "who-we-are": 8,
        "why": 5,
    }
    for token, value in preferred_tokens.items():
        if token in path:
            score += value
    score -= path.count("/") * 2
    if len(path) <= 1:
        score -= 20
    return score


def _is_ignorable_internal_path(url: str) -> bool:
    path = urlparse(url).path.lower()
    ignored_tokens = (
        "privacy",
        "terms",
        "cookie",
        "cookies",
        "login",
        "signin",
        "sign-in",
        "wp-admin",
        "tag/",
        "author/",
        "feed",
        "category/",
        "page/",
        "cart",
        "checkout",
    )
    ignored_suffixes = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf", ".zip")
    return any(token in path for token in ignored_tokens) or path.endswith(ignored_suffixes)
