"""Appends every action to logs/actions.jsonl (one JSON object per line)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ActionLogger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def log(
        self,
        *,
        command: str,
        skill: str | None,
        params: dict[str, Any] | None,
        confirmed: bool | None,   # None = no confirmation needed
        ok: bool,
        reply: str,
        **extra: Any,             # e.g. timings={...}, follow_up=True
    ) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "command": command,
            "skill": skill,
            "params": params or {},
            "confirmed": confirmed,
            "ok": ok,
            "reply": reply,
            **extra,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
