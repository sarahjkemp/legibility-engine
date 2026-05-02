from __future__ import annotations

from urllib.parse import urlparse


def infer_founder_name(founder_linkedin_url: str | None, founder_name: str | None) -> str | None:
    if founder_name:
        return founder_name.strip() or None
    if not founder_linkedin_url:
        return None
    path = urlparse(founder_linkedin_url).path.strip("/")
    if not path:
        return None
    slug = path.split("/")[-1]
    if not slug:
        return None
    words = [part for part in slug.replace("_", "-").split("-") if part and part.lower() not in {"in", "pub"}]
    if not words:
        return None
    return " ".join(word.capitalize() for word in words[:4])
