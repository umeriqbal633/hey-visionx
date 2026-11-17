"""Personal speech fixes from config/corrections.yaml: words speech-to-text keeps getting
wrong -> what you meant (e.g. `gronkolo: chrome kholo`). Applied to voice transcripts only."""
from __future__ import annotations

import re
from pathlib import Path

import yaml


def load_corrections(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.BaseLoader) or {}
    fixes = data.get("corrections", data) if isinstance(data, dict) else {}
    return {str(k).strip(): str(v).strip() for k, v in (fixes or {}).items() if str(k).strip()}


def apply_corrections(text: str, fixes: dict[str, str]) -> str:
    """Whole-word, case-insensitive replacements; longest phrases first."""
    for wrong in sorted(fixes, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(wrong)}(?!\w)", fixes[wrong], text, flags=re.IGNORECASE)
    return text
