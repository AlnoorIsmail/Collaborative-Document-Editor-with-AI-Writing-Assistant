from pathlib import Path

import pytest

from app.backend.schemas.ai import AIInteractionCreateRequest
from app.backend.services.ai.prompt_builder import PromptTemplateRenderer


def test_default_prompts_directory_contains_expected_templates() -> None:
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"

    assert prompts_dir.exists()
    assert (prompts_dir / "chat_assistant.txt").exists()
    assert (prompts_dir / "rewrite.txt").exists()
    assert (prompts_dir / "summarize.txt").exists()
    assert (prompts_dir / "translate.txt").exists()


def test_renderer_renders_template_with_payload_values() -> None:
    renderer = PromptTemplateRenderer()
    payload = AIInteractionCreateRequest(
        feature_type="rewrite",
        scope_type="selection",
        selected_text_snapshot="Fix this sentence.",
        surrounding_context="Paragraph above.",
        user_instruction="Make it concise.",
        base_revision=3,
        parameters={"tone": "formal", "limit": 2},
    )

    result = renderer.render(payload)

    assert "Rewrite the provided document content" in result
    assert "FEATURE_TYPE:\nrewrite" in result
    assert "SCOPE_TYPE:\nselection" in result
    assert "DOCUMENT_TEXT:\nFix this sentence." in result
    assert "ADDITIONAL_CONTEXT:\nParagraph above." in result
    assert "USER_INSTRUCTION:\nMake it concise." in result
    assert 'PARAMETERS_JSON:\n{"limit": 2, "tone": "formal"}' in result


def test_renderer_uses_fallback_template_for_missing_feature_type(
    tmp_path: Path,
) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "chat_assistant.txt").write_text(
        "fallback {feature_type} {selected_text_snapshot} {parameters_json}",
        encoding="utf-8",
    )

    renderer = PromptTemplateRenderer(prompts_dir=prompts_dir)
    payload = AIInteractionCreateRequest(
        feature_type="grammar-fix",
        scope_type="document",
        selected_text_snapshot="Needs help.",
        base_revision=1,
        parameters={},
    )

    assert renderer.render(payload) == "fallback grammar-fix Needs help. {}"


def test_renderer_uses_configured_prompts_directory_instead_of_hardcoded_files(
    tmp_path: Path,
) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "chat_assistant.txt").write_text("unused", encoding="utf-8")
    (prompts_dir / "rewrite.txt").write_text(
        "custom {feature_type} {user_instruction} {selected_text_snapshot}",
        encoding="utf-8",
    )

    renderer = PromptTemplateRenderer(prompts_dir=prompts_dir)
    payload = AIInteractionCreateRequest(
        feature_type="rewrite",
        scope_type="document",
        selected_text_snapshot="Original text",
        user_instruction="Keep the meaning",
        base_revision=0,
        parameters={},
    )

    assert renderer.render(payload) == "custom rewrite Keep the meaning Original text"


def test_renderer_normalizes_blank_optional_values() -> None:
    renderer = PromptTemplateRenderer()
    payload = AIInteractionCreateRequest(
        feature_type="summarize",
        scope_type="document",
        selected_text_snapshot="Body text",
        surrounding_context="   ",
        user_instruction=None,
        base_revision=0,
        parameters={},
    )

    result = renderer.render(payload)

    assert "FOCUS_INSTRUCTION:\nNot provided." in result
    assert "ADDITIONAL_CONTEXT:\nNot provided." in result
    assert "PARAMETERS_JSON:\n{}" in result


def test_renderer_raises_when_no_template_and_no_fallback_exist(tmp_path: Path) -> None:
    renderer = PromptTemplateRenderer(prompts_dir=tmp_path)
    payload = AIInteractionCreateRequest(
        feature_type="rewrite",
        scope_type="document",
        selected_text_snapshot="Body text",
        base_revision=0,
        parameters={},
    )

    with pytest.raises(FileNotFoundError):
        renderer.render(payload)
