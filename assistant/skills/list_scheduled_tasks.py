"""List the user's scheduled tasks."""
from __future__ import annotations

from assistant.core.schedules import load_tasks
from assistant.skills import _schedules
from assistant.skills.base import Result, Skill


class ListScheduledTasks(Skill):
    name = "list_scheduled_tasks"
    description = ("List the user's scheduled tasks, e.g. 'mere scheduled tasks batao', "
                   "'what have I scheduled?'.")
    parameters = {"type": "object", "properties": {}}
    risk = "safe"

    def describe(self, **_) -> str:
        return "list scheduled tasks"

    def run(self, **_) -> Result:
        tasks = load_tasks(_schedules.schedules_path(self.config))
        if not tasks:
            return Result(True, "You don't have any scheduled tasks.")
        missing = []
        try:
            scheduler = _schedules.make_scheduler()
            missing = [t for t in tasks if not scheduler.exists(t)]
        except Exception:
            pass
        count = "1 scheduled task" if len(tasks) == 1 else f"{len(tasks)} scheduled tasks"
        reply = f"You have {count}: {_schedules.numbered(tasks)}."
        if missing:
            reply += f" Warning: {len(missing)} of them is missing from Windows Task Scheduler."
        return Result(True, reply)
