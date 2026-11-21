"""Gemini provider transport behaviour, exercised offline by faking urlopen."""

import io
import json

import pytest

from gar.models import EvalCase
from gar.providers.gemini import GeminiProvider


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _ok_payload():
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Calling the tool."},
                        {"functionCall": {"name": "get_weather", "args": {"city": "Lahore"}}},
                    ]
                }
            }
        ],
        "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30},
    }


def _case():
    return EvalCase(
        id="tool-basic",
        prompt="Weather in Lahore?",
        tools=[{"name": "get_weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}],
        expected_tool="get_weather",
    )


def test_successful_call_parses_text_tools_and_usage(monkeypatch):
    def fake_urlopen(request, timeout=None):
        return FakeResponse(json.dumps(_ok_payload()).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
    turn = provider.complete(_case())

    assert turn.ok
    assert turn.text == "Calling the tool."
    assert [c.name for c in turn.tool_calls] == ["get_weather"]
    assert turn.tool_calls[0].args == {"city": "Lahore"}
    assert turn.usage.input_tokens == 120
    assert turn.usage.output_tokens == 30
    assert turn.attempts == 1
    assert turn.backoff_ms == []


def test_transient_errors_are_retried_with_growing_backoff(monkeypatch):
    state = {"calls": 0}

    class HTTPError503(Exception):
        code = 503

    import urllib.error

    def fake_urlopen(request, timeout=None):
        state["calls"] += 1
        if state["calls"] < 3:
            raise urllib.error.HTTPError("url", 503, "unavailable", {}, None)
        return FakeResponse(json.dumps(_ok_payload()).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: None)

    provider = GeminiProvider(api_key="test-key", max_attempts=3, base_delay_s=0.1, jitter=False)
    turn = provider.complete(_case())

    assert turn.ok
    assert turn.attempts == 3
    assert len(turn.backoff_ms) == 2
    assert turn.backoff_ms[1] >= turn.backoff_ms[0] * 1.5


def test_non_retryable_status_returns_error_turn_without_sleeping(monkeypatch):
    import urllib.error

    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError("url", 400, "bad request", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = GeminiProvider(api_key="test-key", max_attempts=3)
    turn = provider.complete(_case())

    assert not turn.ok
    assert turn.attempts == 1
    assert "HTTP 400" in turn.error


def test_missing_key_produces_an_error_turn(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    provider = GeminiProvider(api_key=None)
    turn = provider.complete(_case())
    assert not turn.ok
    assert "GEMINI_API_KEY" in turn.error


def test_payload_includes_tools_and_schema():
    provider = GeminiProvider(api_key="k")
    case = EvalCase(
        id="c",
        prompt="p",
        tools=[{"name": "t", "description": "d", "parameters": {"type": "object"}}],
        output_schema={"type": "object", "properties": {"a": {"type": "string"}}},
    )
    payload = provider._payload(case)
    assert payload["tools"][0]["functionDeclarations"][0]["name"] == "t"
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseSchema" in payload["generationConfig"]
