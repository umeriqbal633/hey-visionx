"""Groq provider (OpenAI-style tool calling), free tier.

- The API key is passed explicitly; it is read from .env and never put into os.environ.
- Every API failure becomes a one-sentence BrainError instead of a crash.
- Settings live under `brain.groq` in settings.yaml.
"""
from __future__ import annotations

import json
from typing import Any

import groq

from assistant.core.config import Config
from assistant.core.providers.base import BrainError, Provider, ProviderResponse


class GroqProvider(Provider):
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024,
                 reasoning_effort: str | None = None, temperature: float = 0.2,
                 client: Any = None) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.temperature = temperature
        self.client = client or groq.Groq(api_key=api_key, max_retries=1, timeout=20.0)

    @staticmethod
    def to_groq_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"type": "function",
             "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
            for t in tools
        ]

    def choose(self, system: str, tools: list[dict[str, Any]], command: str) -> ProviderResponse:
        extra: dict[str, Any] = {}
        if self.reasoning_effort:  # only for reasoning models (e.g. openai/gpt-oss-*)
            extra["reasoning_effort"] = self.reasoning_effort
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": command}],
                tools=self.to_groq_tools(tools),
                tool_choice="auto",
                temperature=self.temperature,
                max_completion_tokens=self.max_tokens,
                **extra,
            )
        except groq.AuthenticationError as e:
            raise BrainError("My Groq key was rejected, so please check GROQ_API_KEY in .env.") from e
        except groq.PermissionDeniedError as e:
            raise BrainError("This Groq key isn't allowed to use that model.") from e
        except groq.NotFoundError as e:
            raise BrainError(f"The Groq model '{self.model}' wasn't found, so please check settings.yaml.") from e
        except groq.RateLimitError as e:
            raise BrainError("Groq's free tier is rate limiting me right now, so please try again in a minute.") from e
        except groq.BadRequestError as e:
            raise BrainError("The brain couldn't handle that request, so please try rephrasing it.") from e
        except groq.InternalServerError as e:
            raise BrainError("The Groq service is busy right now, so please try again shortly.") from e
        except groq.APIStatusError as e:
            raise BrainError(f"Groq returned an error ({e.status_code}), so please try again.") from e
        except groq.APIConnectionError as e:
            raise BrainError("I can't reach Groq, so please check your internet connection.") from e

        message = response.choices[0].message
        for call in message.tool_calls or []:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError as e:
                raise BrainError("The brain gave me a garbled answer, so please try again.") from e
            return ProviderResponse(tool_name=call.function.name, tool_input=args if isinstance(args, dict) else {})

        text = (message.content or "").strip()
        if not text:
            raise BrainError("I didn't get an answer, so please try again.")
        return ProviderResponse(text=text)


def create(config: Config) -> GroqProvider:
    settings = config.brain.get("groq", {})
    key_name = settings.get("api_key_env", "GROQ_API_KEY")
    api_key = config.secret(key_name)
    if not api_key:
        raise BrainError(f"No Groq key found, so please add {key_name} to the .env file.")
    model = settings.get("model")
    if not model:
        raise BrainError("No Groq model is set, so please add brain.groq.model to settings.yaml.")
    return GroqProvider(
        api_key=api_key,
        model=model,
        max_tokens=int(settings.get("max_tokens", 1024)),
        reasoning_effort=settings.get("reasoning_effort"),
        temperature=float(settings.get("temperature", 0.2)),
    )
