"""Delete one scheduled task (asks for a yes first)."""
from __future__ import annotations

from assistant.core.schedules import load_tasks, save_tasks
from assistant.skills import _schedules
from assistant.skills.base import Result, Skill


class DeleteScheduledTask(Skill):
    name = "delete_scheduled_task"
    description = ("Delete one of the user's scheduled tasks, e.g. '9 baje wala task delete karo', "
                   "'cancel the good morning schedule', 'delete task 2'.")
    parameters = {
        "type": "object",
        "properties": {
            "which": {"type": "string",
                      "description": "How the user identified the task: its number, its time, or words from it."},
        },
        "required": ["which"],
    }
    risk = "confirm"

    def _find(self, which: str):
        return _schedules.find_task(load_tasks(_schedules.schedules_path(self.config)), which)

    def describe(self, which: str = "", **_) -> str:
        return f"delete the scheduled task '{which}'"

    def check(self, which: str = "", **_) -> str | None:
        _, question = self._find(which)
        return question

    def confirm_prompt(self, which: str = "", **_) -> str:
        task, question = self._find(which)
        return f"Delete the scheduled task '{task.description}'?" if task else (question or "")

    def run(self, which: str = "", **_) -> Result:
        task, question = self._find(which)
        if task is None:
            return Result(False, question or "I couldn't find that task.")
        try:
            _schedules.make_scheduler().delete(task)    # fine if Windows no longer has it
        except Exception:
            pass
        path = _schedules.schedules_path(self.config)
        save_tasks(path, [t for t in load_tasks(path) if t.id != task.id])
        return Result(True, f"Deleted the scheduled task: {task.description}.")
