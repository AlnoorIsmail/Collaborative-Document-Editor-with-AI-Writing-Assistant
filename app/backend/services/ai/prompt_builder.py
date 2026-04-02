"""Prompt template rendering for AI suggestion requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.backend.schemas.ai import AIInteractionCreateRequest


class PromptTemplateRenderer:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._prompts_dir = prompts_dir or Path(__file__).resolve().parents[2] / "prompts"

    def render(self, payload: AIInteractionCreateRequest) -> str:
        template = self._load_template(payload.feature_type)
        return template.format(
            feature_type=payload.feature_type,
            scope_type=payload.scope_type,
            selected_text_snapshot=self._value_or_default(payload.selected_text_snapshot),
            surrounding_context=self._value_or_default(payload.surrounding_context),
            user_instruction=self._value_or_default(payload.user_instruction),
            parameters_json=self._parameters_json(payload.parameters),
        )

    def _load_template(self, feature_type: str) -> str:
        normalized = feature_type.strip().lower().replace("-", "_")
        candidate = self._prompts_dir / f"{normalized}.txt"
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

        fallback = self._prompts_dir / "chat_assistant.txt"
        return fallback.read_text(encoding="utf-8")

    def _value_or_default(self, value: str | None) -> str:
        if value is None:
            return "Not provided."

        stripped = value.strip()
        return stripped or "Not provided."

    def _parameters_json(self, parameters: dict[str, Any]) -> str:
        if not parameters:
            return "{}"
        return json.dumps(parameters, ensure_ascii=True, sort_keys=True)
