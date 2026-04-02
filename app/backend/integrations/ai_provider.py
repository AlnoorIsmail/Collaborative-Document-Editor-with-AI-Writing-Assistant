"""Provider seam for future AI model integration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


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
        # TODO: Replace with provider-specific retry, timeout, and error mapping logic.
        del feature_type, prompt
        return GeneratedSuggestion(
            generated_output="More formal rewritten paragraph",
            model_name="gpt-x",
        )
