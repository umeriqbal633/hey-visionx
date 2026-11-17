import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import groq
import httpx
import pytest

from assistant.core.providers import groq as provider_mod
from assistant.core.providers.base import BrainError
from assistant.core.providers.groq import GroqProvider, create

TOOLS = [{"name": "open_app", "description": "Open an app.",
          "parameters": {"type": "object", "properties": {"app": {"type": "string"}}}}]


def completion(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def call(name, arguments):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


def make(client, effort="low"):
    return GroqProvider(api_key="k", model="openai/gpt-oss-120b", reasoning_effort=effort, client=client)


@pytest.fixture
def groq_config(config):
    config.settings["brain"] = {"provider": "groq",
                                "groq": {"model": "openai/gpt-oss-120b", "reasoning_effort": "low"}}
    config.secrets = {"GROQ_API_KEY": "gsk-test"}
    return config


def test_create_passes_key_explicitly(groq_config, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with patch.object(provider_mod.groq, "Groq") as cls:
        p = create(groq_config)
    assert cls.call_args.kwargs["api_key"] == "gsk-test"
    assert p.model == "openai/gpt-oss-120b" and p.reasoning_effort == "low"


def test_missing_key_is_one_sentence(groq_config, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    groq_config.secrets = {}
    with pytest.raises(BrainError, match="GROQ_API_KEY"):
        create(groq_config)


def test_request_shape():
    client = MagicMock()
    client.chat.completions.create.return_value = completion(tool_calls=[call("open_app", '{"app": "chrome"}')])
    make(client).choose("SYSTEM", TOOLS, "chrome kholo")
    kw = client.chat.completions.create.call_args.kwargs
    assert kw["model"] == "openai/gpt-oss-120b"
    assert kw["messages"] == [{"role": "system", "content": "SYSTEM"},
                              {"role": "user", "content": "chrome kholo"}]
    assert kw["tools"] == [{"type": "function", "function": {
        "name": "open_app", "description": "Open an app.", "parameters": TOOLS[0]["parameters"]}}]
    assert kw["tool_choice"] == "auto" and kw["reasoning_effort"] == "low"


def test_no_reasoning_effort_for_non_reasoning_models():
    client = MagicMock()
    client.chat.completions.create.return_value = completion("hi")
    make(client, effort=None).choose("S", TOOLS, "x")
    assert "reasoning_effort" not in client.chat.completions.create.call_args.kwargs


def test_parses_tool_call_and_keeps_urdu():
    client = MagicMock()
    client.chat.completions.create.return_value = completion(
        tool_calls=[call("send_whatsapp", '{"contact": "Ali", "message": "میں لیٹ ہوں"}')])
    r = make(client).choose("S", TOOLS, "x")
    assert r.tool_name == "send_whatsapp" and r.tool_input["message"] == "میں لیٹ ہوں"


def test_parses_text_reply():
    client = MagicMock()
    client.chat.completions.create.return_value = completion("Kis app ko kholna hai?")
    r = make(client).choose("S", TOOLS, "kholo")
    assert r.tool_name is None and r.text == "Kis app ko kholna hai?"


def test_garbled_arguments_become_brain_error():
    client = MagicMock()
    client.chat.completions.create.return_value = completion(tool_calls=[call("open_app", "{not json")])
    with pytest.raises(BrainError):
        make(client).choose("S", TOOLS, "x")


def test_retries_once_on_tool_use_failed():
    client = MagicMock()
    req = httpx.Request("POST", "https://api.groq.com")
    failed = groq.BadRequestError("tool_use_failed", response=httpx.Response(400, request=req),
                                  body={"error": {"code": "tool_use_failed"}})
    client.chat.completions.create.side_effect = [failed, completion("ok")]
    assert make(client).choose("S", TOOLS, "x").text == "ok"
    assert client.chat.completions.create.call_count == 2


def test_other_bad_requests_are_not_retried():
    client = MagicMock()
    req = httpx.Request("POST", "https://api.groq.com")
    client.chat.completions.create.side_effect = groq.BadRequestError(
        "bad model param", response=httpx.Response(400, request=req), body={"error": {"code": "invalid"}})
    with pytest.raises(BrainError):
        make(client).choose("S", TOOLS, "x")
    assert client.chat.completions.create.call_count == 1


def _status_error(cls, code):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return cls("boom", response=httpx.Response(code, request=request), body=None)


@pytest.mark.parametrize("exc, phrase", [
    (lambda: _status_error(groq.RateLimitError, 429), "rate limiting"),
    (lambda: _status_error(groq.AuthenticationError, 401), "GROQ_API_KEY"),
    (lambda: _status_error(groq.NotFoundError, 404), "wasn't found"),
    (lambda: _status_error(groq.BadRequestError, 400), "rephrasing"),
    (lambda: _status_error(groq.InternalServerError, 503), "busy"),
    (lambda: groq.APIConnectionError(request=httpx.Request("POST", "https://api.groq.com")), "internet"),
])
def test_api_errors_become_one_sentence(exc, phrase):
    client = MagicMock()
    client.chat.completions.create.side_effect = exc()
    with pytest.raises(BrainError, match=phrase) as info:
        make(client).choose("S", TOOLS, "x")
    msg = str(info.value)
    assert msg.endswith(".") and not re.search(r"[.!?]\s", msg)


def test_real_settings_select_groq_and_keep_anthropic():
    from assistant.core.config import CONFIG_DIR, load_config
    cfg = load_config(CONFIG_DIR, CONFIG_DIR / "missing.env")
    assert cfg.brain["provider"] == "groq"
    assert cfg.brain["model"] == "claude-haiku-5-5"          # anthropic settings untouched
    assert cfg.brain["groq"]["model"] == "openai/gpt-oss-120b"
