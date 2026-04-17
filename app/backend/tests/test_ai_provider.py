from app.backend.integrations.ai_provider import StubAIProviderClient


def _prompt(*, document_text: str, user_instruction: str = "") -> str:
    return f"""FEATURE_TYPE:
rewrite

SCOPE_TYPE:
document

USER_INSTRUCTION:
{user_instruction or "Not provided."}

DOCUMENT_TEXT:
{document_text}

ADDITIONAL_CONTEXT:
Not provided.
"""


def test_stub_summary_returns_polished_document_based_summary() -> None:
    provider = StubAIProviderClient()

    result = provider.generate_suggestion(
        feature_type="summarize",
        prompt=_prompt(
            document_text=(
                "i cant attend the meeting tomorrow because i am sick. "
                "please send me notes after."
            )
        ),
    )

    assert result.model_name == "local-summary-fallback"
    assert result.usage is not None
    assert result.usage.prompt_tokens > 0
    assert result.usage.completion_tokens > 0
    assert result.usage.total_tokens == (
        result.usage.prompt_tokens + result.usage.completion_tokens
    )
    assert (
        result.generated_output
        == "I cannot attend the meeting tomorrow because I am sick. Please send me notes after."
    )


def test_stub_rewrite_uses_document_text_and_formal_instruction() -> None:
    provider = StubAIProviderClient()

    result = provider.generate_suggestion(
        feature_type="rewrite",
        prompt=_prompt(
            document_text=(
                "i cant attend the meeting tomorrow because i am sick. "
                "please send me notes after."
            ),
            user_instruction="Make this more formal and clear.",
        ),
    )

    assert result.model_name == "local-rewrite-fallback"
    assert result.usage is not None
    assert result.usage.prompt_tokens > 0
    assert result.usage.completion_tokens > 0
    assert result.usage.total_tokens == (
        result.usage.prompt_tokens + result.usage.completion_tokens
    )
    assert (
        result.generated_output
        == "I am unable to attend the meeting tomorrow because I am unwell. Please share the notes with me afterward."
    )
