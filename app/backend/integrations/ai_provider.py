"""Provider seam for future AI model integration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
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

TRANSLATION_FALLBACKS: dict[str, dict[str, str]] = {
    "spanish": {
        "hello": "hola",
        "meeting": "reunion",
        "document": "documento",
        "summary": "resumen",
        "risk": "riesgo",
        "action": "accion",
        "plan": "plan",
        "team": "equipo",
        "draft": "borrador",
    },
    "french": {
        "hello": "bonjour",
        "meeting": "reunion",
        "document": "document",
        "summary": "resume",
        "risk": "risque",
        "action": "action",
        "plan": "plan",
        "team": "equipe",
        "draft": "brouillon",
    },
}

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
    usage: "GeneratedSuggestionUsage"


@dataclass(frozen=True)
class GeneratedSuggestionUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None = None


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
        normalized_feature = feature_type.strip().lower().replace("-", "_")
        if normalized_feature == "summarize":
            output = self._summarize(prompt)
            return GeneratedSuggestion(
                generated_output=output,
                model_name="local-summary-fallback",
                usage=self._estimate_usage(prompt=prompt, completion=output),
            )

        if normalized_feature == "chat_assistant":
            output = self._chat_assistant(prompt)
            return GeneratedSuggestion(
                generated_output=output,
                model_name="local-chat-assistant-fallback",
                usage=self._estimate_usage(prompt=prompt, completion=output),
            )

        if normalized_feature == "translate":
            output = self._translate(prompt)
            return GeneratedSuggestion(
                generated_output=output,
                model_name="local-translate-fallback",
                usage=self._estimate_usage(prompt=prompt, completion=output),
            )

        if normalized_feature in {"grammar_fix", "fix_grammar", "grammar"}:
            output = self._grammar_fix(prompt)
            return GeneratedSuggestion(
                generated_output=output,
                model_name="local-grammar-fallback",
                usage=self._estimate_usage(prompt=prompt, completion=output),
            )

        if normalized_feature in {"expand", "elaborate"}:
            output = self._expand(prompt)
            return GeneratedSuggestion(
                generated_output=output,
                model_name="local-expand-fallback",
                usage=self._estimate_usage(prompt=prompt, completion=output),
            )

        if normalized_feature in {"restructure", "reorganize"}:
            output = self._restructure(prompt)
            return GeneratedSuggestion(
                generated_output=output,
                model_name="local-restructure-fallback",
                usage=self._estimate_usage(prompt=prompt, completion=output),
            )

        output = self._rewrite(prompt)
        return GeneratedSuggestion(
            generated_output=output,
            model_name="local-rewrite-fallback",
            usage=self._estimate_usage(prompt=prompt, completion=output),
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

    def _chat_assistant(self, prompt: str) -> str:
        source_text = self._extract_source_text(prompt)
        instruction = self._extract_instruction(prompt)

        if not source_text and not instruction:
            return "Ask a question or provide document text for AI help."

        if not source_text:
            return self._sentence_case(instruction.strip())

        summary = self._summarize(prompt)
        if not instruction:
            return summary

        cleaned_instruction = self._sentence_case(instruction.strip())
        return f"{cleaned_instruction} Relevant context: {summary}"

    def _translate(self, prompt: str) -> str:
        source_text = self._extract_source_text(prompt)
        if not source_text:
            return "No document content was available to translate."

        parameters = self._extract_parameters(prompt)
        target_language = str(
            parameters.get("target_language")
            or parameters.get("language")
            or self._extract_instruction(prompt)
            or "Spanish"
        ).strip()
        normalized_language = target_language.lower()
        translated = self._translate_words(source_text, language=normalized_language)
        readable_language = target_language[0].upper() + target_language[1:] if target_language else "Spanish"
        return f"Translated to {readable_language}: {translated}"

    def _grammar_fix(self, prompt: str) -> str:
        source_text = self._extract_source_text(prompt)
        if not source_text:
            return "No document content was available to improve."

        parameters = self._extract_parameters(prompt)
        style = str(parameters.get("style") or "preserve").lower()
        return self._polish_text(source_text, formal=style == "formal")

    def _expand(self, prompt: str) -> str:
        source_text = self._extract_source_text(prompt)
        if not source_text:
            return "No document content was available to expand."

        polished = self._polish_text(source_text)
        parameters = self._extract_parameters(prompt)
        detail_level = str(parameters.get("detail_level") or "medium").lower()
        instruction = self._extract_instruction(prompt)

        expansion_by_level = {
            "light": " Add one clarifying detail so the reader understands the main point faster.",
            "medium": " Add useful context, explain why it matters, and make the idea easier to act on.",
            "detailed": " Add context, practical implications, and a concrete next step so the idea feels complete.",
        }
        suffix = expansion_by_level.get(detail_level, expansion_by_level["medium"])
        if instruction:
            suffix += f" Focus on: {self._sentence_case(instruction.strip())}"
        return f"{polished}{suffix}"

    def _restructure(self, prompt: str) -> str:
        source_text = self._extract_source_text(prompt)
        if not source_text:
            return "No document content was available to restructure."

        polished = self._polish_text(source_text)
        sentences = self._split_sentences(polished)
        if len(sentences) <= 1:
            return f"Overview: {polished}\n\nNext step: Clarify the main takeaway and supporting detail."

        opening = sentences[0]
        supporting = " ".join(sentences[1:])
        return f"Overview: {opening}\n\nDetails: {supporting}"

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

    def _extract_parameters(self, prompt: str) -> dict[str, str]:
        raw_parameters = self._extract_section(prompt, "PARAMETERS_JSON")
        if not raw_parameters or raw_parameters == "{}":
            return {}

        try:
            import json

            payload = json.loads(raw_parameters)
        except ValueError:
            return {}

        if not isinstance(payload, dict):
            return {}

        return {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(key, str) and value is not None
        }

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

    def _estimate_usage(
        self, *, prompt: str, completion: str
    ) -> GeneratedSuggestionUsage:
        prompt_tokens = self._estimate_tokens(prompt)
        completion_tokens = self._estimate_tokens(completion)
        return GeneratedSuggestionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    def _estimate_tokens(self, text: str) -> int:
        normalized = text.strip()
        if not normalized:
            return 0
        return max(1, math.ceil(len(normalized) / 4))

    def _translate_words(self, text: str, *, language: str) -> str:
        dictionary = TRANSLATION_FALLBACKS.get(language)
        if not dictionary:
            return self._polish_text(text)

        parts = re.split(r"(\W+)", text)
        translated_parts: list[str] = []
        for part in parts:
            key = part.lower()
            replacement = dictionary.get(key)
            if replacement is None:
                translated_parts.append(part)
                continue

            if part.istitle():
                translated_parts.append(replacement.capitalize())
            elif part.isupper():
                translated_parts.append(replacement.upper())
            else:
                translated_parts.append(replacement)

        return "".join(translated_parts)


class OpenAICompatibleAIProviderClient(AIProviderClient):
    def __init__(
        self,
        *,
        api_key: str,
        api_url: str,
        model_name: str,
        timeout_seconds: float,
        prompt_token_cost_per_1k: float = 0.0,
        completion_token_cost_per_1k: float = 0.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._api_url = api_url.strip()
        self._model_name = model_name.strip()
        self._timeout_seconds = timeout_seconds
        self._prompt_token_cost_per_1k = prompt_token_cost_per_1k
        self._completion_token_cost_per_1k = completion_token_cost_per_1k

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
            usage=self._extract_usage(payload, prompt=prompt, completion=generated_output),
        )

    def _system_instruction(self, feature_type: str) -> str:
        normalized_feature = feature_type.strip().lower().replace("-", "_")
        if normalized_feature == "summarize":
            return (
                "You summarize collaborative documents. Respond with the summary only, "
                "without markdown or meta commentary."
            )

        if normalized_feature == "chat_assistant":
            return (
                "You are a helpful document assistant. Answer the user's request using "
                "the provided document text as the primary source, and respond with plain "
                "text only."
            )

        if normalized_feature == "translate":
            return (
                "You translate document text while preserving meaning and readability. "
                "Return only the translated text without markdown or commentary."
            )

        if normalized_feature in {"grammar_fix", "fix_grammar", "grammar"}:
            return (
                "You improve grammar, spelling, and clarity while preserving the writer's "
                "meaning. Return only the improved text."
            )

        if normalized_feature in {"expand", "elaborate"}:
            return (
                "You expand document text with useful detail and context while staying "
                "consistent with the source. Return only the improved text."
            )

        if normalized_feature in {"restructure", "reorganize"}:
            return (
                "You reorganize document text to improve flow and readability. Return only "
                "the reorganized text."
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

    def _extract_usage(
        self,
        payload: dict,
        *,
        prompt: str,
        completion: str,
    ) -> GeneratedSuggestionUsage:
        usage = payload.get("usage")
        if isinstance(usage, dict):
            prompt_tokens = self._coerce_token_count(usage.get("prompt_tokens"))
            completion_tokens = self._coerce_token_count(usage.get("completion_tokens"))
            total_tokens = self._coerce_token_count(usage.get("total_tokens"))
            if total_tokens == 0:
                total_tokens = prompt_tokens + completion_tokens
            return GeneratedSuggestionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=self._estimate_cost(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                ),
            )

        prompt_tokens = self._estimate_tokens(prompt)
        completion_tokens = self._estimate_tokens(completion)
        return GeneratedSuggestionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=self._estimate_cost(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )

    def _estimate_cost(
        self, *, prompt_tokens: int, completion_tokens: int
    ) -> float | None:
        total_cost = (
            (prompt_tokens / 1000) * self._prompt_token_cost_per_1k
            + (completion_tokens / 1000) * self._completion_token_cost_per_1k
        )
        if total_cost <= 0:
            return None
        return round(total_cost, 6)

    def _coerce_token_count(self, value: object) -> int:
        if isinstance(value, int) and value >= 0:
            return value
        return 0

    def _estimate_tokens(self, text: str) -> int:
        normalized = text.strip()
        if not normalized:
            return 0
        return max(1, math.ceil(len(normalized) / 4))
