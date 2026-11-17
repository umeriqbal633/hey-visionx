"""Shared helpers for the scheduling skills (leading underscore: not a skill itself)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from assistant.core.config import CONFIG_DIR, Config
from assistant.core.matching import similarity
from assistant.core.schedules import ScheduleError, ScheduledTask, clock_text, load_tasks, parse_time
from assistant.core.scheduler_windows import WindowsScheduler

SCHEDULING_SKILLS = frozenset({"schedule_task", "list_scheduled_tasks", "delete_scheduled_task"})


def schedules_path(config: Config) -> Path:
    custom = config.settings.get("scheduler", {}).get("file")
    return Path(custom) if custom else CONFIG_DIR / "schedules.yaml"


def make_scheduler() -> WindowsScheduler:   # replaced in tests
    return WindowsScheduler()


def now() -> datetime:                       # replaced in tests
    return datetime.now()


def numbered(tasks: list[ScheduledTask]) -> str:
    return "; ".join(f"{i}) {t.description}" for i, t in enumerate(tasks, 1))


def find_task(tasks: list[ScheduledTask], which: str) -> tuple[ScheduledTask | None, str | None]:
    """Pick the task the user means: its number in the list, its time ('9 baje'), or words
    from its description. Exactly one match -> (task, None); otherwise (None, question)."""
    if not tasks:
        return None, "You don't have any scheduled tasks."
    w = (which or "").strip()
    digits = w.rstrip(".").removeprefix("#").strip()
    if digits.isdigit() and 1 <= int(digits) <= len(tasks) and len(digits) <= 2:
        return tasks[int(digits) - 1], None
    hits: list[ScheduledTask] = []
    try:
        at = parse_time(w).strftime("%H:%M")
        times = {at}
        if "am" not in w.lower() and "pm" not in w.lower() and int(at[:2]) < 12:
            times.add(f"{int(at[:2]) + 12:02d}:{at[3:]}")  # "9 baje" may mean 9 AM or 9 PM
        hits = [t for t in tasks if t.time in times]
    except ScheduleError:
        pass
    if not hits:
        scored = sorted(((similarity(w, t.description), t) for t in tasks), key=lambda x: -x[0])
        top = scored[0][0]
        hits = [t for s, t in scored if s >= 0.5 and s >= top - 0.1]
    if len(hits) == 1:
        return hits[0], None
    if hits:
        return None, f"Which task do you mean: {numbered(hits)}?"
    return None, f"I couldn't find that task; you have: {numbered(tasks)}."


__all__ = ["SCHEDULING_SKILLS", "schedules_path", "make_scheduler", "now", "numbered", "find_task",
           "load_tasks", "clock_text"]
