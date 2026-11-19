"""What Windows Task Scheduler runs at a task's time:

    pythonw -m assistant.run_task <task id>

Runs the task's stored, already-approved skill + params (no LLM, no new question), logs the
result with "scheduled": true, and speaks a one-line result if `scheduler.announce` is on.
One-time tasks are removed after they run.
"""
from __future__ import annotations

import sys

from assistant.core.config import LOG_FILE, Config, load_config
from assistant.core.logger import ActionLogger
from assistant.core.registry import discover
from assistant.core.runlock import one_at_a_time
from assistant.core.schedules import load_tasks, save_tasks
from assistant.skills import _schedules
from assistant.skills.base import Result


LOCK_FILE = LOG_FILE.parent / "run_task.lock"


def run(task_id: str, config: Config, logger: ActionLogger, speak=None, lock_file=None) -> Result:
    path = _schedules.schedules_path(config)
    tasks = load_tasks(path)
    task = next((t for t in tasks if t.id == task_id), None)
    if task is None:
        result = Result(False, f"Scheduled task {task_id} no longer exists, so I removed it from Windows.")
        try:
            from assistant.core.schedules import ScheduledTask
            _schedules.make_scheduler().delete(ScheduledTask(task_id, "once", "00:00", "", {}))
        except Exception:
            pass
        logger.log(command=f"[scheduled {task_id}]", skill=None, params=None, confirmed=None,
                   ok=False, reply=result.reply, scheduled=True, task_id=task_id)
        return result

    # Scheduled sends may start WhatsApp from cold: give it longer than an interactive send.
    sched = config.settings.get("scheduler", {})
    config.settings.setdefault("whatsapp", {})["window_timeout"] = sched.get("whatsapp_timeout", 30)

    skill = discover(config).get(task.skill)
    if skill is None or task.skill in _schedules.SCHEDULING_SKILLS:
        result = Result(False, f"The scheduled task uses an unknown skill '{task.skill}'.")
        speak_now = speak
    else:
        with one_at_a_time(lock_file or LOCK_FILE):          # tasks at the same minute take turns
            try:
                result = skill.run(**task.params)
            except Exception:
                result = Result(False, f"Something went wrong while running {task.skill}.")
            if speak and sched.get("announce", True):
                speak(f"Scheduled task: {result.reply}")
        speak_now = None

    logger.log(command=f"[scheduled {task.id}] {task.description}", skill=task.skill, params=task.params,
               confirmed=True, ok=result.ok, reply=result.reply, scheduled=True, task_id=task.id)

    if task.repeat == "once":
        save_tasks(path, [t for t in load_tasks(path) if t.id != task.id])
        try:
            _schedules.make_scheduler().delete(task)
        except Exception:
            pass

    if speak_now and sched.get("announce", True):
        speak_now(f"Scheduled task: {result.reply}")
    return result


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        return 2
    config = load_config()

    def speak(text: str) -> None:
        from assistant.interfaces.tts import Speaker
        tts = config.settings.get("tts", {})
        Speaker(voice=tts.get("voice"), rate=tts.get("rate")).say(text)

    result = run(args[0], config, ActionLogger(LOG_FILE), speak)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
