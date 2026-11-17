"""Windows Task Scheduler (built in, free) through schtasks.exe. Argument lists only, no shell.
Tasks run as the logged-in user ("Interactive only"); no admin rights needed."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from assistant.core.config import PROJECT_DIR
from assistant.core.schedules import ScheduledTask, task_xml

Runner = Callable[[list[str]], subprocess.CompletedProcess]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=30,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def python_for_tasks() -> str:
    """pythonw.exe from the same venv (no console window pops up), else python.exe."""
    exe = Path(sys.executable)
    windowless = exe.with_name("pythonw.exe")
    return str(windowless if windowless.exists() else exe)


class WindowsScheduler:
    def __init__(self, runner: Runner = _run, python: str | None = None, workdir: Path = PROJECT_DIR) -> None:
        self.runner = runner
        self.python = python or python_for_tasks()
        self.workdir = workdir

    def create(self, task: ScheduledTask) -> bool:
        xml = task_xml(task, self.python, f"-m assistant.run_task {task.id}", str(self.workdir))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{task.id}.xml"
            path.write_text(xml, encoding="utf-16")
            result = self.runner(["schtasks", "/Create", "/TN", task.windows_name, "/XML", str(path), "/F"])
        return result.returncode == 0

    def delete(self, task: ScheduledTask) -> bool:
        result = self.runner(["schtasks", "/Delete", "/TN", task.windows_name, "/F"])
        return result.returncode == 0

    def exists(self, task: ScheduledTask) -> bool:
        return self.runner(["schtasks", "/Query", "/TN", task.windows_name]).returncode == 0
