"""LLM providers. Add one by dropping <name>.py here with a `create(config)` function."""
from __future__ import annotations

import importlib

from assistant.core.config import Config
from assistant.core.providers.base import BrainError, Provider


def get_provider(config: Config) -> Provider:
    name = config.brain.get("provider", "anthropic")
    try:
        module = importlib.import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as e:
        raise BrainError(f"Unknown brain provider '{name}' in settings.yaml.") from e
    return module.create(config)
