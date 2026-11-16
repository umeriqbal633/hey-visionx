"""Loads YAML config files and secrets.

Secrets are read from .env with dotenv_values(), which returns a dict and does NOT
copy anything into os.environ. That keeps VisionX's key out of the environment
that child processes (like Claude Code in Phase 4) inherit.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

from assistant.core.contacts import Contact, load_contacts

PACKAGE_DIR = Path(__file__).resolve().parent.parent  # .../assistant
PROJECT_DIR = PACKAGE_DIR.parent                      # repo root
CONFIG_DIR = PACKAGE_DIR / "config"
LOG_FILE = PACKAGE_DIR / "logs" / "actions.jsonl"
ENV_FILE = PROJECT_DIR / ".env"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


@dataclass
class Config:
    settings: dict[str, Any] = field(default_factory=dict)
    apps: dict[str, Any] = field(default_factory=dict)
    websites: dict[str, Any] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)
    contacts: list[Contact] | None = None   # None = contacts.yaml doesn't exist yet

    @property
    def assistant_name(self) -> str:
        return self.settings.get("assistant", {}).get("name", "VisionX")

    @property
    def company(self) -> str:
        return self.settings.get("assistant", {}).get("company", "")

    @property
    def brain(self) -> dict[str, Any]:
        return self.settings.get("brain", {})

    def secret(self, name: str) -> str | None:
        """Value from .env first, then the real environment as a fallback."""
        value = self.secrets.get(name) or os.environ.get(name)
        return value or None


def load_config(config_dir: Path = CONFIG_DIR, env_file: Path = ENV_FILE) -> Config:
    secrets = {k: v for k, v in dotenv_values(env_file).items() if v} if env_file.exists() else {}
    return Config(
        settings=load_yaml(config_dir / "settings.yaml"),
        apps=load_yaml(config_dir / "apps.yaml"),
        websites=load_yaml(config_dir / "websites.yaml"),
        secrets=secrets,
        contacts=load_contacts(config_dir / "contacts.yaml"),
    )
