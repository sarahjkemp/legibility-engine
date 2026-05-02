from __future__ import annotations

from ..config import EngineSettings
from .transport import get_json


async def lookup_entity(company_name: str, settings: EngineSettings, limit: int = 3) -> list[dict]:
    safe_name = company_name.replace('"', '\\"')
    query = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item rdfs:label ?label .
      FILTER(LANG(?label) = "en")
      FILTER(CONTAINS(LCASE(?label), LCASE("{safe_name}")))
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT {limit}
    """
    payload = await get_json(
        "https://query.wikidata.org/sparql",
        settings,
        params={"format": "json", "query": query},
        headers={"Accept": "application/sparql-results+json"},
        cache_namespace="wikidata_search",
    )
    bindings = ((payload or {}).get("results") or {}).get("bindings") or []
    results = []
    for item in bindings:
        uri = (((item.get("item") or {}).get("value")) or "").strip()
        label = (((item.get("itemLabel") or {}).get("value")) or "").strip()
        if not uri or not label:
            continue
        results.append({"id": uri.rsplit("/", 1)[-1], "label": label, "url": uri})
    return results
