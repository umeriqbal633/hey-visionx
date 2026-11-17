"""Scheduled tasks: the model, config/schedules.yaml (git-ignored), time/date parsing and the
Windows Task Scheduler XML for each task.

A task stores an already-approved skill + params. At run time nothing is re-interpreted by
the LLM: assistant.run_task just runs that skill with those params.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import yaml

REPEATS = ("once", "daily", "weekdays", "weekly")
DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DAY_ALIASES = {
    **{k: i for i, k in enumerate(DAY_KEYS)},
    **{n.lower(): i for i, n in enumerate(DAY_NAMES)},
    # Urdu / Roman Urdu day names
    "peer": 0, "pir": 0, "mangal": 1, "budh": 2, "jumerat": 3, "jumeraat": 3,
    "juma": 4, "jumma": 4, "hafta": 5, "itwar": 6, "itwaar": 6,
}


class ScheduleError(ValueError):
    """A one-sentence problem with a requested schedule (shown to the user)."""


@dataclass
class ScheduledTask:
    id: str
    repeat: str                      # once | daily | weekdays | weekly
    time: str                        # "HH:MM", 24h
    skill: str
    params: dict[str, Any] = field(default_factory=dict)
    date: str | None = None          # "YYYY-MM-DD": the run date (once) or first run (repeating)
    days: list[str] = field(default_factory=list)   # weekly: ["mon", "wed"]
    description: str = ""
    created: str = ""

    @property
    def windows_name(self) -> str:
        return f"VisionX\\{self.id}"


# --- parsing --------------------------------------------------------------------------------
def parse_time(text: str) -> time:
    """'09:00', '9:00', '9', '9am', '9:30 pm', '21:15', '9 baje' -> time. Raises ScheduleError."""
    t = (text or "").strip().lower().replace(".", ":")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a m|p m)?(?:\s*baje)?", t)
    if not m:
        raise ScheduleError(f"I couldn't understand the time '{text}'.")
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").replace(" ", "")
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ScheduleError(f"'{text}' isn't a valid time.")
    return time(hour, minute)


def parse_days(days: list[str] | str | None) -> list[str]:
    items = days.replace(",", " ").split() if isinstance(days, str) else list(days or [])
    out = []
    for d in items:
        key = str(d).strip().lower()
        if key not in DAY_ALIASES:
            raise ScheduleError(f"I don't know the day '{d}'.")
        k = DAY_KEYS[DAY_ALIASES[key]]
        if k not in out:
            out.append(k)
    return sorted(out, key=DAY_KEYS.index)


def resolve_date(text: str | None, at: time, now: datetime) -> date:
    """When a one-time task should run. 'today'/'aaj', 'tomorrow'/'kal', 'parson',
    'YYYY-MM-DD' or a weekday name; empty = the next time `at` comes round."""
    t = (text or "").strip().lower()
    today = now.date()
    if not t:
        return today if datetime.combine(today, at) > now else today + timedelta(days=1)
    if t in ("today", "aaj"):
        return today
    if t in ("tomorrow", "kal"):
        return today + timedelta(days=1)
    if t in ("day after tomorrow", "parson", "parso"):
        return today + timedelta(days=2)
    if t in DAY_ALIASES:
        ahead = (DAY_ALIASES[t] - today.weekday()) % 7
        d = today + timedelta(days=ahead)
        return d if datetime.combine(d, at) > now else d + timedelta(days=7)
    try:
        return date.fromisoformat(t)
    except ValueError:
        raise ScheduleError(f"I couldn't understand the date '{text}'.") from None


def first_run(repeat: str, at: time, now: datetime, days: list[str]) -> date:
    """First date a repeating task fires (today if its time is still ahead)."""
    d = now.date() if datetime.combine(now.date(), at) > now else now.date() + timedelta(days=1)
    allowed = {"daily": range(7), "weekdays": range(5)}.get(repeat) or [DAY_KEYS.index(k) for k in days]
    while d.weekday() not in allowed:
        d += timedelta(days=1)
    return d


def build_task(repeat: str, time_text: str, skill: str, params: dict[str, Any], now: datetime,
               date_text: str | None = None, days: list[str] | str | None = None,
               action_text: str = "") -> ScheduledTask:
    repeat = (repeat or "once").strip().lower()
    if repeat not in REPEATS:
        raise ScheduleError(f"I can schedule once, daily, on weekdays or weekly, not '{repeat}'.")
    at = parse_time(time_text)
    day_list = parse_days(days) if repeat == "weekly" else []
    if repeat == "weekly" and not day_list:
        raise ScheduleError("Which days of the week should it run?")
    if repeat == "once":
        run_date = resolve_date(date_text, at, now)
        if datetime.combine(run_date, at) <= now:
            raise ScheduleError("That time has already passed, so please give a later time.")
    else:
        run_date = first_run(repeat, at, now, day_list)
    task = ScheduledTask(id=secrets.token_hex(3), repeat=repeat, time=at.strftime("%H:%M"), skill=skill,
                         params=dict(params), date=run_date.isoformat(), days=day_list,
                         created=now.isoformat(timespec="seconds"))
    task.description = f"{describe_when(task, now)}: {action_text}" if action_text else describe_when(task, now)
    return task


# --- wording --------------------------------------------------------------------------------
def clock_text(hhmm: str) -> str:
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def join_and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def describe_when(task: ScheduledTask, now: datetime | None = None) -> str:
    at = clock_text(task.time)
    if task.repeat == "daily":
        return f"Every day at {at}"
    if task.repeat == "weekdays":
        return f"Every weekday at {at}"
    if task.repeat == "weekly":
        return f"Every {join_and([DAY_NAMES[DAY_KEYS.index(d)] for d in task.days])} at {at}"
    d = date.fromisoformat(task.date)
    if now is not None and d == now.date():
        return f"Today at {at}"
    if now is not None and d == now.date() + timedelta(days=1):
        return f"Tomorrow at {at}"
    return f"On {d.strftime('%A')} {d.day} {d.strftime('%B')} at {at}"


# --- storage --------------------------------------------------------------------------------
def load_tasks(path: Path) -> list[ScheduledTask]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    tasks = []
    for t in data.get("tasks") or []:
        try:
            tasks.append(ScheduledTask(**{k: v for k, v in t.items() if k in ScheduledTask.__dataclass_fields__}))
        except TypeError:
            continue
    return tasks


def save_tasks(path: Path, tasks: list[ScheduledTask]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "# VisionX scheduled tasks (git-ignored). Manage them by voice; each one is also in\n" \
             "# Windows Task Scheduler under the 'VisionX' folder.\n"
    body = yaml.safe_dump({"tasks": [asdict(t) for t in tasks]}, allow_unicode=True, sort_keys=False)
    path.write_text(header + body, encoding="utf-8")


# --- Windows Task Scheduler XML ---------------------------------------------------------------
def task_xml(task: ScheduledTask, command: str, arguments: str, workdir: str) -> str:
    start = f"{task.date}T{task.time}:00"
    if task.repeat == "once":
        trigger = f"<TimeTrigger><StartBoundary>{start}</StartBoundary><Enabled>true</Enabled></TimeTrigger>"
    elif task.repeat == "daily":
        trigger = (f"<CalendarTrigger><StartBoundary>{start}</StartBoundary><Enabled>true</Enabled>"
                   f"<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger>")
    else:
        keys = list(DAY_KEYS[:5]) if task.repeat == "weekdays" else task.days
        days = "".join(f"<{DAY_NAMES[DAY_KEYS.index(k)]} />" for k in keys)
        trigger = (f"<CalendarTrigger><StartBoundary>{start}</StartBoundary><Enabled>true</Enabled>"
                   f"<ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek>{days}</DaysOfWeek>"
                   f"</ScheduleByWeek></CalendarTrigger>")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>{escape("VisionX: " + task.description)}</Description></RegistrationInfo>
  <Triggers>{trigger}</Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <StartWhenAvailable>true</StartWhenAvailable>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec><Command>{escape(command)}</Command><Arguments>{escape(arguments)}</Arguments><WorkingDirectory>{escape(workdir)}</WorkingDirectory></Exec></Actions>
</Task>
"""
