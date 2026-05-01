from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover
    AsyncAnthropic = None

from ..config import EngineSettings


class AnthropicJSONClient:
    def __init__(self, settings: EngineSettings, model: str = "claude-sonnet-4-6") -> None:
        self.settings = settings
        self.model = model
        self._client = (
            AsyncAnthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key and AsyncAnthropic is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self._client is not None

    async def run_prompt(self, prompt_path: Path, input_payload: dict[str, Any]) -> dict[str, Any] | None:
        if self._client is None:
            return None
        prompt = prompt_path.read_text(encoding="utf-8")
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=1200,
            temperature=0,
            system=prompt,
            messages=[{"role": "user", "content": json.dumps(input_payload)}],
        )
        text_blocks = [block.text for block in message.content if getattr(block, "type", None) == "text"]
        if not text_blocks:
            return None
        combined = "\n".join(text_blocks).strip()
        return json.loads(_extract_json_object(combined))


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    if start == -1:
        return stripped

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]

    return stripped
