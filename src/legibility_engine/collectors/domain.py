from __future__ import annotations

from datetime import datetime

try:
    import whois
except ImportError:  # pragma: no cover
    whois = None


def lookup_domain_age_years(domain: str) -> float | None:
    if whois is None:
        return None
    try:
        data = whois.whois(domain)
    except Exception:
        return None
    creation_date = data.creation_date
    if isinstance(creation_date, list):
        creation_date = next((item for item in creation_date if isinstance(item, datetime)), None)
    if not isinstance(creation_date, datetime):
        return None
    return round((datetime.now(tz=creation_date.tzinfo) - creation_date).days / 365.25, 2)
