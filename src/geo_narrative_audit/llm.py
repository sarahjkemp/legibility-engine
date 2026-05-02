from __future__ import annotations

import json

try:
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover
    AsyncAnthropic = None

from .settings import AppSettings


SYSTEM_PROMPT = """You are a strategic analyst evaluating whether a brand's owned channels tell one clear story that AI systems can retrieve and restate.

Return valid JSON only.

Schema:
{
  "channel_summaries": [{"key": "string", "message": "string"}],
  "narrative_spine": ["string"],
  "where_the_story_breaks": ["string"],
  "website_findings": ["string"],
  "narrative_consistency": 0-10,
  "website_geo_readiness": 0-10,
  "spokesperson_alignment": 0-10,
  "diagnosis": "string",
  "retrieval_impact": "string",
  "rationale": ["string"],
  "what_to_fix_first": [
    {
      "title": "string",
      "why_it_matters": "string",
      "what_to_do": "string"
    }
  ]
}
"""


class AuditLLM:
    def __init__(self, settings: AppSettings, model: str = "claude-sonnet-4-6") -> None:
        self._client = (
            AsyncAnthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key and AsyncAnthropic is not None
            else None
        )
        self.model = model

    @property
    def available(self) -> bool:
        return self._client is not None

    async def analyze(self, payload: dict) -> dict | None:
        if self._client is None:
            return None
        message = await self._client.messages.create(
            model=self.model,
            temperature=0,
            max_tokens=1800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        text = "\n".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        ).strip()
        if not text:
            return None
        return json.loads(_extract_json(text))


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped
