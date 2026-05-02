from __future__ import annotations

from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..config import EngineSettings
from .transport import get_text


async def search_companies_house(query: str, settings: EngineSettings, limit: int = 5) -> list[dict]:
    text = await get_text(
        f"https://find-and-update.company-information.service.gov.uk/search/companies?q={quote_plus(query)}",
        settings,
        cache_namespace="companies_house_search",
    )
    soup = BeautifulSoup(text, "html.parser")
    results: list[dict] = []
    for item in soup.select(".type-company, #results li"):
        anchor = item.select_one("a")
        if not anchor:
            continue
        href = anchor.get("href")
        name = anchor.get_text(" ", strip=True)
        description = item.get_text(" ", strip=True)
        if not href or not name:
            continue
        results.append(
            {
                "name": name,
                "url": f"https://find-and-update.company-information.service.gov.uk{href}",
                "description": description,
            }
        )
        if len(results) >= limit:
            break
    return results


async def fetch_company_profile(profile_url: str, settings: EngineSettings) -> dict:
    text = await get_text(profile_url, settings, cache_namespace="companies_house_profile")
    soup = BeautifulSoup(text, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    address = _text_after_label(soup, "Registered office address")
    sic = _text_after_label(soup, "Nature of business (SIC)")
    incorporation = _text_after_label(soup, "Incorporated on")
    return {
        "url": profile_url,
        "page_text": page_text,
        "registered_address": address,
        "sic": sic,
        "incorporated_on": incorporation,
    }


def _text_after_label(soup: BeautifulSoup, label: str) -> str | None:
    node = soup.find(string=lambda text: text and label.lower() in text.lower())
    if not node or not node.parent:
        return None
    parent = node.parent
    sibling = parent.find_next_sibling()
    if sibling:
        return sibling.get_text(" ", strip=True) or None
    text = parent.get_text(" ", strip=True)
    return text if text and text != label else None
