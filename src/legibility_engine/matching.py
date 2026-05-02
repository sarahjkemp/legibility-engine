from __future__ import annotations

import re
from urllib.parse import urlparse


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
