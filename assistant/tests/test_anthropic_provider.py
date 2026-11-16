import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx2
import pytest

from assistant.core.providers import anthropic as provider_mod
from assistant.core.providers.anthropic import AnthropicProvider, create
from assistant.core.providers.base import BrainError

TOOLS = [{"name": "open_app", "description": "Open an app.",
          "parameters": {"type": "object", "properties": {"app": {"type": "string"}}}}]


def fake_response(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def tool_block(name, inp):
    return SimpleNamespace(type="tool_use", name=name, input=inp)


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def make(client):
    return AnthropicProvider(api_key="k", model="claude-haiku-5-5", effort="low", client=client)


def test_create_passes_key_explicitly(config, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch.object(provider_mod.anthropic, "Anthropic") as cls:
        p = create(config)
    assert cls.call_args.kwargs["api_key"] == "test-key"
    assert p.model == "claude-haiku-5-5"


def test_create_without_key_is_one_sentence_error(config, monkeypatch):
    monkeypatch.delenv("VISIONX_ANTHROPIC_KEY", raising=False)
    config.secrets = {}
    with pytest.raises(BrainError, match="VISIONX_ANTHROPIC_KEY"):
        create(config)


def test_create_ignores_anthropic_api_key_env(config, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-be-used")
    monkeypatch.delenv("VISIONX_ANTHROPIC_KEY", raising=False)
    config.secrets = {}
    with pytest.raises(BrainError):
        create(config)


def test_refuses_anthropic_api_key_as_key_name(config):
    config.settings["brain"]["api_key_env"] = "ANTHROPIC_API_KEY"
    with pytest.raises(BrainError):
        create(config)


def test_request_shape_uses_caching_and_tools():
    client = MagicMock()
    client.messages.create.return_value = fake_response(tool_block("open_app", {"app": "chrome"}))
    make(client).choose("SYSTEM", TOOLS, "chrome kholo")

    kw = client.messages.create.call_args.kwargs
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["system"] == [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}]
    assert kw["tools"] == [{"name": "open_app", "description": "Open an app.",
                            "input_schema": TOOLS[0]["parameters"]}]
    assert kw["tool_choice"]["type"] == "auto"
    assert kw["output_config"] == {"effort": "low"}
    assert kw["messages"] == [{"role": "user", "content": "chrome kholo"}]


def test_parses_tool_call():
    client = MagicMock()
    client.messages.create.return_value = fake_response(
        text_block("Sure."), tool_block("open_app", {"app": "chrome"}))
    r = make(client).choose("S", TOOLS, "chrome kholo")
    assert r.tool_name == "open_app" and r.tool_input == {"app": "chrome"}


def test_parses_text_reply():
    client = MagicMock()
    client.messages.create.return_value = fake_response(text_block("Kaunsi app kholun?"))
    r = make(client).choose("S", TOOLS, "kholo")
    assert r.tool_name is None and r.text == "Kaunsi app kholun?"


def test_refusal_becomes_brain_error():
    client = MagicMock()
    client.messages.create.return_value = fake_response(stop_reason="refusal")
    with pytest.raises(BrainError):
        make(client).choose("S", TOOLS, "x")


def _status_error(cls, code):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(code, request=request), body=None)


@pytest.mark.parametrize("exc, phrase", [
    (lambda: _status_error(anthropic.RateLimitError, 429), "rate limited"),
    (lambda: _status_error(anthropic.AuthenticationError, 401), "API key"),
    (lambda: _status_error(anthropic.NotFoundError, 404), "wasn't found"),
    (lambda: _status_error(anthropic.InternalServerError, 500), "busy"),
    (lambda: _status_error(anthropic.InternalServerError, 529), "busy"),
    (lambda: anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com")), "internet"),
])
def test_api_errors_become_one_sentence(exc, phrase):
    client = MagicMock()
    client.messages.create.side_effect = exc()
    with pytest.raises(BrainError, match=phrase) as info:
        make(client).choose("S", TOOLS, "x")
    msg = str(info.value)
    assert msg.endswith(".") and not re.search(r"[.!?]\s", msg)  # exactly one sentence
