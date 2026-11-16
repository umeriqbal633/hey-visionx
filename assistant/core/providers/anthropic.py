"""Anthropic (Claude) provider using tool use.

- The API key is passed explicitly; nothing is read from ANTHROPIC_API_KEY.
- The tool list + system prompt are cached (one breakpoint on the system block;
  tools render before system, so both are covered).
- Every API failure becomes a one-sentence BrainError instead of a crash.
"""
from __future__ import annotations

from typing import Any

import anthropic

from assistant.core.config import Config
from assistant.core.providers.base import BrainError, Provider, ProviderResponse


class AnthropicProvider(Provider):
    def __init__(self, api_key: str, model: str, effort: str = "low", max_tokens: int = 2048,
                 client: Any = None) -> None:
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.client = client or anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=30.0)

    @staticmethod
    def to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]

    def choose(self, system: str, tools: list[dict[str, Any]], command: str) -> ProviderResponse:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                tools=self.to_anthropic_tools(tools),
                tool_choice={"type": "auto", "disable_parallel_tool_use": True},
                output_config={"effort": self.effort},
                messages=[{"role": "user", "content": command}],
            )
        except anthropic.AuthenticationError as e:
            raise BrainError("My API key was rejected, so please check VISIONX_ANTHROPIC_KEY in .env.") from e
        except anthropic.PermissionDeniedError as e:
            raise BrainError("This API key isn't allowed to use that model.") from e
        except anthropic.NotFoundError as e:
            raise BrainError(f"The model '{self.model}' wasn't found, so please check settings.yaml.") from e
        except anthropic.RateLimitError as e:
            raise BrainError("I'm being rate limited right now, so please try again in a minute.") from e
        except anthropic.BadRequestError as e:
            raise BrainError("The brain rejected that request, so please try rephrasing it.") from e
        except anthropic.InternalServerError as e:
            raise BrainError("The brain service is busy right now, so please try again shortly.") from e
        except anthropic.APIStatusError as e:
            raise BrainError(f"The brain returned an error ({e.status_code}), so please try again.") from e
        except anthropic.APIConnectionError as e:
            raise BrainError("I can't reach the brain, so please check your internet connection.") from e

        if response.stop_reason == "refusal":
            raise BrainError("Sorry, I can't help with that one.")

        for block in response.content:
            if block.type == "tool_use":
                return ProviderResponse(tool_name=block.name, tool_input=dict(block.input or {}))

        text = " ".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise BrainError("I didn't get an answer, so please try again.")
        return ProviderResponse(text=text)


def create(config: Config) -> AnthropicProvider:
    brain = config.brain
    key_name = brain.get("api_key_env", "VISIONX_ANTHROPIC_KEY")
    if key_name == "ANTHROPIC_API_KEY":
        raise BrainError("Don't use ANTHROPIC_API_KEY for VisionX; name it VISIONX_ANTHROPIC_KEY.")
    api_key = config.secret(key_name)
    if not api_key:
        raise BrainError(f"No API key found, so please add {key_name} to the .env file.")
    return AnthropicProvider(
        api_key=api_key,
        model=brain.get("model", "claude-haiku-5-5"),
        effort=brain.get("effort", "low"),
        max_tokens=int(brain.get("max_tokens", 2048)),
    )
