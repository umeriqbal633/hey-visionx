"""Auto-discovers skills: every Skill subclass in the assistant.skills package."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Any

import assistant.skills as skills_pkg
from assistant.core.config import Config
from assistant.skills.base import Skill


class Registry:
    def __init__(self, skills: list[Skill]) -> None:
        # Sorted so the tool list is byte-identical on every request (prompt caching).
        self._skills = {s.name: s for s in sorted(skills, key=lambda s: s.name)}

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def names(self) -> list[str]:
        return list(self._skills)

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [s.tool_schema() for s in self._skills.values()]

    def attach(self, brain: Any) -> None:
        """Give every skill access to the brain and this registry (e.g. schedule_task turns
        'Saad ko good morning bhejo' into an exact skill call at creation time)."""
        for skill in self._skills.values():
            skill.brain, skill.registry = brain, self


def discover(config: Config, package: ModuleType = skills_pkg) -> Registry:
    found: list[Skill] = []
    for info in pkgutil.iter_modules(package.__path__):
        if info.name == "base" or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, Skill)
                and cls is not Skill
                and cls.__module__ == module.__name__
                and not inspect.isabstract(cls)
            ):
                found.append(cls(config))
    return Registry(found)
