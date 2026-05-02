from __future__ import annotations

from ..collectors.search import search_web
from ..collectors.site import fetch_internal_pages
from ..config import AuditConfig, EngineSettings
from ..models import AuditTarget, SubScoreFinding, SubScoreResult
from .common import evidence

BODY_CANDIDATES = ["PRCA", "CIPR", "ICAEW", "SRA", "Forbes Councils"]


async def run(target: AuditTarget, config: AuditConfig, settings: EngineSettings) -> SubScoreResult:
    pages = await fetch_internal_pages(str(target.primary_url), settings, limit=4)
    site_text = " ".join(page.get("text", "")[:2000] for page in pages)
    found = [body for body in BODY_CANDIDATES if body.lower() in site_text.lower()]
    verified = []
    for body in found:
        results = await search_web(f'"{body}" "{target.company_name}"', settings, limit=3)
        if results:
            verified.append({"body": body, "result": results[0]})
    count = len(verified)
    score = 0.0 if count == 0 else 50.0 if count == 1 else 80.0 if count == 2 else 100.0
    return SubScoreResult(
        score=score,
        confidence=0.65 if found else 0.4,
        evidence=[evidence(item["result"]["url"], f'{item["body"]}: {item["result"].get("title") or ""}') for item in verified[:6]],
        findings=[SubScoreFinding(severity="medium" if count == 0 else "low", text=f"{count} public professional or regulatory recognitions were verified.")],
        raw_data={"found_bodies": found, "verified": verified},
    )
