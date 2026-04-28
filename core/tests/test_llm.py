from types import SimpleNamespace

import pytest

from core.llm import _extract_json_object, openrouter_chat_json


def test_openrouter_chat_json_requires_api_key(settings):
    settings.OPENROUTER_API_KEY = ""

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY must be configured"):
        openrouter_chat_json(model="test-model", system_prompt="system", user_prompt="user")


def test_openrouter_chat_json_posts_expected_request(settings, mocker):
    settings.OPENROUTER_API_KEY = "test-key"
    settings.OPENROUTER_API_BASE = "https://openrouter.example/api/v1/"
    settings.OPENROUTER_APP_URL = "https://newsletter-maker.example"
    settings.OPENROUTER_APP_NAME = "newsletter-maker"
    settings.AI_REQUEST_TIMEOUT_SECONDS = 12.5

    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"choices": [{"message": {"content": '{"summary": "Hello"}'}}]},
    )
    post_mock = mocker.patch("core.llm.httpx.post", return_value=response)
    mocker.patch("core.llm.time.perf_counter", side_effect=[1.0, 1.123])

    result = openrouter_chat_json(
        model="openrouter/test-model",
        system_prompt="Return JSON.",
        user_prompt="Summarize this.",
    )

    assert result.payload == {"summary": "Hello"}
    assert result.model == "openrouter/test-model"
    assert result.latency_ms == 123
    assert post_mock.call_args.args[0] == "https://openrouter.example/api/v1/chat/completions"
    assert post_mock.call_args.kwargs["headers"] == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://newsletter-maker.example",
        "X-OpenRouter-Title": "newsletter-maker",
    }
    assert post_mock.call_args.kwargs["json"] == {
        "model": "openrouter/test-model",
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": "Summarize this."},
        ],
    }
    assert post_mock.call_args.kwargs["timeout"] == 12.5


def test_extract_json_object_accepts_direct_json_object():
    assert _extract_json_object('{"score": 0.7}') == {"score": 0.7}


def test_extract_json_object_extracts_embedded_json_object_from_text():
    assert _extract_json_object('Here is the result:\n```json\n{"score": 0.7}\n```') == {"score": 0.7}


def test_extract_json_object_rejects_missing_json_object():
    with pytest.raises(ValueError, match="did not contain a JSON object"):
        _extract_json_object("No JSON here.")


def test_extract_json_object_rejects_non_object_json():
    with pytest.raises(ValueError, match="JSON must be an object"):
        _extract_json_object('["not", "an", "object"]')