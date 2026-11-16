"""Tell the current local time."""
from __future__ import annotations

from datetime import datetime

from assistant.skills.base import Result, Skill


def _now() -> datetime:
    return datetime.now()


class GetTime(Skill):
    name = "get_time"
    description = "Tell the user the current local time and date."
    parameters = {"type": "object", "properties": {}}
    risk = "safe"

    def run(self, **_) -> Result:
        now = _now()
        clock = now.strftime("%I:%M %p").lstrip("0")
        return Result(True, f"It's {clock} on {now.strftime('%A')}, {now.day} {now.strftime('%B')}.")
