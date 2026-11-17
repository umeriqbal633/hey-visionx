"""Create a scheduled (one-time or repeating) task.

At creation the command is turned into an exact skill call (via the brain), checked like a
normal command (contact exists, etc.) and read back in full. The user's yes approves every
future run; at run time the stored skill + params are executed as they are.
"""
from __future__ import annotations

import json
from typing import Any

from assistant.core.schedules import ScheduleError, ScheduledTask, build_task, load_tasks, save_tasks
from assistant.skills import _schedules
from assistant.skills.base import Result, Skill


class ScheduleTask(Skill):
    name = "schedule_task"
    description = (
        "Schedule a command to run later, once or repeatedly, e.g. 'har roz subah 9 baje Saad ko "
        "good morning bhejo', 'every weekday at 8:30 YouTube kholo', 'kal 5 baje Ammi ko message "
        "karo ke main aa raha hoon', 'remind... ' style tasks that are one of the other actions. "
        "Use only when the user gives a time or repetition for the action."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The action itself in the user's own words and language, WITHOUT the time "
                               "part, e.g. 'Saad ko good morning bhejo'. Keep message words exactly.",
            },
            "time": {"type": "string",
                     "description": "Time of day as 24-hour HH:MM, e.g. '09:00', '17:30'. "
                                    "subah = morning, dopahar = afternoon, shaam = evening, raat = night."},
            "repeat": {"type": "string", "enum": ["once", "daily", "weekdays", "weekly"],
                       "description": "once, daily (har roz / every day), weekdays (Mon-Fri), "
                                      "or weekly on the given days."},
            "date": {"type": ["string", "null"],
                     "description": "For once: 'today', 'tomorrow', a weekday name, or YYYY-MM-DD. "
                                    "Leave empty for the next time that clock time comes round."},
            "days": {"type": ["array", "null"], "items": {"type": "string"},
                     "description": "For weekly: English day names, e.g. ['monday', 'thursday']."},
        },
        "required": ["command", "time", "repeat"],
    }
    risk = "confirm"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._plans: dict[str, ScheduledTask] = {}

    @staticmethod
    def _key(params: dict[str, Any]) -> str:
        return json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)

    def _plan(self, **params: Any) -> tuple[ScheduledTask | None, str | None]:
        """Turn the request into an exact task (cached so the read-back and the saved task match)."""
        key = self._key(params)
        if key in self._plans:
            return self._plans[key], None
        if self.brain is None or self.registry is None:
            return None, "Scheduling isn't available right now."
        command = str(params.get("command") or "").strip()
        decision = self.brain.decide(command)
        if not decision.skill:
            return None, decision.reply or "What should I do at that time?"
        if decision.skill in _schedules.SCHEDULING_SKILLS:
            return None, "I can't schedule scheduling itself; tell me the action to run."
        inner = self.registry.get(decision.skill)
        if inner is None:
            return None, "I don't have a skill for that yet."
        missing = [p for p in inner.parameters.get("required", []) if not str(decision.params.get(p, "")).strip()]
        if missing:
            return None, f"What {' and '.join(missing)} should the scheduled task use?"
        question = inner.check(**decision.params)
        if question:
            return None, getattr(question, "text", question)
        try:
            task = build_task(params.get("repeat") or "once", str(params.get("time") or ""),
                              inner.name, decision.params, _schedules.now(),
                              date_text=params.get("date"), days=params.get("days"),
                              action_text=inner.describe(**decision.params))
        except ScheduleError as e:
            return None, str(e)
        self._plans[key] = task
        return task, None

    def check(self, **params: Any) -> str | None:
        _, question = self._plan(**params)
        return question

    def confirm_prompt(self, **params: Any) -> str:
        task, question = self._plan(**params)
        return f"{task.description}. Schedule it?" if task else (question or "")

    def run(self, **params: Any) -> Result:
        task, question = self._plan(**params)
        self._plans.pop(self._key(params), None)
        if task is None:
            return Result(False, question or "I couldn't set up that schedule.")
        path = _schedules.schedules_path(self.config)
        tasks = load_tasks(path)
        tasks.append(task)
        save_tasks(path, tasks)
        try:
            ok = _schedules.make_scheduler().create(task)
        except Exception:
            ok = False
        if not ok:
            save_tasks(path, [t for t in tasks if t.id != task.id])
            return Result(False, "Windows Task Scheduler didn't accept the task, so nothing was scheduled.")
        return Result(True, f"Scheduled: {task.description[0].lower()}{task.description[1:]}.")
