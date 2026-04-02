"""Provider seam for future AI model integration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re

import httpx

COMMON_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bcan't\b", "cannot"),
    (r"\bcant\b", "cannot"),
    (r"\bwon't\b", "will not"),
    (r"\bwont\b", "will not"),
    (r"\bdon't\b", "do not"),
    (r"\bdont\b", "do not"),
    (r"\bi'm\b", "I am"),
    (r"\bim\b", "I am"),
    (r"\bit's\b", "it is"),
)

FORMAL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bi cannot attend\b", "I am unable to attend"),
    (r"\bbecause I am sick\b", "because I am unwell"),
    (
        r"\bplease send me the notes after\b",
        "please share the notes with me afterward",
    ),
    (r"\bplease send me notes after\b", "please share the notes with me afterward"),
    (r"\bplease send me notes\b", "please share the notes with me"),
)


class AIProviderTimeoutError(Exception):
    pass


class AIProviderUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class GeneratedSuggestion:
    generated_output: str
    model_name: str


class AIProviderClient(ABC):
    @abstractmethod
    def generate_suggestion(
        self, *, feature_type: str, prompt: str
    ) -> GeneratedSuggestion:
        """Generate a reviewable suggestion from an external AI provider."""


class StubAIProviderClient(AIProviderClient):
    def generate_suggestion(
        self, *, feature_type: str, prompt: str
    ) -> GeneratedSuggestion:
        normalized_feature = feature_type.strip().lower()
        if normalized_feature == "summarize":
            return GeneratedSuggestion(
                generated_output=self._summarize(prompt),
                model_name="local-summary-fallback",
            )

        return GeneratedSuggestion(
            generated_output=self._rewrite(prompt),
            model_name="local-rewrite-fallback",
        )

    def _summarize(self, prompt: str) -> str:
        source_text = self._extract_source_text(prompt)
        if not source_text:
            return "No document content was available to summarize."

        polished = self._polish_text(source_text)
        sentences = self._split_sentences(polished)
        if not sentences:
            return polished

        selected_sentences: list[str] = []
        total_words = 0
        for sentence in sentences:
            selected_sentences.append(sentence)
            total_words += len(sentence.split())
            if len(selected_sentences) >= 2 or total_words >= 40:
                break

        summary = " ".join(selected_sentences)
        return summary.strip()

    def _rewrite(self, prompt: str) -> str:
        source_text = self._extract_source_text(prompt)
        if not source_text:
            return "No document content was available to rewrite."

        instruction = self._extract_instruction(prompt).lower()
        use_formal_tone = any(
            keyword in instruction
            for keyword in ("formal", "professional", "polish", "clear")
        )
        return self._polish_text(source_text, formal=use_formal_tone)

    def _extract_source_text(self, prompt: str) -> str:
        source_text = (
            self._extract_section(prompt, "DOCUMENT_TEXT")
            or self._extract_section(prompt, "ADDITIONAL_CONTEXT")
            or prompt
        )
        normalized = " ".join(source_text.split())
        if not normalized or normalized == "Not provided.":
            return ""
        return normalized

    def _extract_instruction(self, prompt: str) -> str:
        return (
            self._extract_section(prompt, "USER_INSTRUCTION")
            or self._extract_section(prompt, "FOCUS_INSTRUCTION")
            or ""
        )

    def _polish_text(self, text: str, *, formal: bool = False) -> str:
        polished = text.strip()
        for pattern, replacement in COMMON_REPLACEMENTS:
            polished = re.sub(pattern, replacement, polished, flags=re.IGNORECASE)

        polished = re.sub(r"\bi\b", "I", polished, flags=re.IGNORECASE)

        if formal:
            for pattern, replacement in FORMAL_REPLACEMENTS:
                polished = re.sub(pattern, replacement, polished, flags=re.IGNORECASE)

        sentences = self._split_sentences(polished)
        if not sentences:
            return polished
        return " ".join(self._sentence_case(sentence) for sentence in sentences)

    def _split_sentences(self, text: str) -> list[str]:
        return [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if sentence.strip()
        ]

    def _sentence_case(self, sentence: str) -> str:
        normalized = " ".join(sentence.split()).strip()
        if not normalized:
            return ""
        if normalized[-1] not in ".!?":
            normalized += "."
        return normalized[0].upper() + normalized[1:]

    def _extract_section(self, prompt: str, label: str) -> str:
        pattern = rf"{label}:\n(.*?)(?:\n[A-Z_]+:\n|\Z)"
        match = re.search(pattern, prompt, flags=re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()


class OpenAICompatibleAIProviderClient(AIProviderClient):
    def __init__(
        self,
        *,
        api_key: str,
        api_url: str,
        model_name: str,
        timeout_seconds: float,
    ) -> None:
        self._api_key = api_key.strip()
        self._api_url = api_url.strip()
        self._model_name = model_name.strip()
        self._timeout_seconds = timeout_seconds

    def generate_suggestion(
        self, *, feature_type: str, prompt: str
    ) -> GeneratedSuggestion:
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(
                    self._api_url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model_name,
                        "messages": [
                            {
                                "role": "system",
                                "content": self._system_instruction(feature_type),
                            },
                            {
                                "role": "user",
                                "content": prompt,
                            },
                        ],
                        "temperature": 0.2,
                    },
                )
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError from exc
        except httpx.RequestError as exc:
            raise AIProviderUnavailableError from exc

        if response.status_code >= 500:
            raise AIProviderUnavailableError
        if response.status_code >= 400:
            raise AIProviderUnavailableError

        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderUnavailableError from exc

        generated_output = self._extract_message_text(payload)
        if not generated_output:
            raise AIProviderUnavailableError

        return GeneratedSuggestion(
            generated_output=generated_output,
            model_name=str(payload.get("model") or self._model_name),
        )

    def _system_instruction(self, feature_type: str) -> str:
        normalized_feature = feature_type.strip().lower()
        if normalized_feature == "summarize":
            return (
                "You summarize collaborative documents. Respond with the summary only, "
                "without markdown or meta commentary."
            )

        return (
            "You are a collaborative writing assistant. Respond with the requested "
            "suggestion text only, without markdown or meta commentary."
        )

    def _extract_message_text(self, payload: dict) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            return "\n".join(parts).strip()

        return ""
