"""Phase 4: scheduled tasks. Windows Task Scheduler and the clock are mocked."""
import json
import subprocess
from datetime import datetime
from unittest.mock import patch

import pytest

from assistant.core.brain import Decision
from assistant.core.logger import ActionLogger
from assistant.core.registry import discover
from assistant.core.schedules import (ScheduleError, build_task, describe_when, load_tasks, parse_days,
                                      parse_time, resolve_date, save_tasks, task_xml)
from assistant.core.scheduler_windows import WindowsScheduler
from assistant.main import Session
from assistant import run_task as runner

NOW = datetime(2026, 11, 17, 18, 0)   # Tuesday 6 PM


# --- parsing ---------------------------------------------------------------------------------
@pytest.mark.parametrize("text, hhmm", [("09:00", "09:00"), ("9", "09:00"), ("9am", "09:00"),
                                        ("9:30 pm", "21:30"), ("21:15", "21:15"), ("12 am", "00:00"),
                                        ("9 baje", "09:00"), ("17.45", "17:45")])
def test_parse_time(text, hhmm):
    assert parse_time(text).strftime("%H:%M") == hhmm


@pytest.mark.parametrize("bad", ["", "noon-ish", "25:00", "9:75"])
def test_parse_time_rejects(bad):
    with pytest.raises(ScheduleError):
        parse_time(bad)


def test_parse_days_including_urdu_names():
    assert parse_days(["Monday", "jumma", "mon"]) == ["mon", "fri"]
    with pytest.raises(ScheduleError):
        parse_days(["someday"])


def test_resolve_date():
    at = parse_time("17:00")
    assert str(resolve_date("kal", at, NOW)) == "2026-11-18"
    assert str(resolve_date("", at, NOW)) == "2026-11-18"           # 5 PM already passed today
    assert str(resolve_date("", parse_time("20:00"), NOW)) == "2026-11-17"
    assert str(resolve_date("friday", at, NOW)) == "2026-11-20"
    assert str(resolve_date("tuesday", at, NOW)) == "2026-11-24"    # today's 5 PM has passed


def test_build_task_wording():
    t = build_task("daily", "09:00", "send_whatsapp", {"contact": "Ali Khan", "message": "gm"}, NOW,
                   action_text="send 'gm' to Ali Khan")
    assert t.date == "2026-11-18" and t.description == "Every day at 9:00 AM: send 'gm' to Ali Khan"
    w = build_task("weekly", "18:30", "get_time", {}, NOW, days=["mon", "thursday"])
    assert w.days == ["mon", "thu"] and describe_when(w) == "Every Monday and Thursday at 6:30 PM"
    o = build_task("once", "17:00", "get_time", {}, NOW, date_text="tomorrow")
    assert describe_when(o, NOW) == "Tomorrow at 5:00 PM"


def test_build_task_rejects_past_and_missing_days():
    with pytest.raises(ScheduleError, match="already passed"):
        build_task("once", "09:00", "get_time", {}, NOW, date_text="today")
    with pytest.raises(ScheduleError, match="Which days"):
        build_task("weekly", "09:00", "get_time", {}, NOW)
    with pytest.raises(ScheduleError):
        build_task("hourly", "09:00", "get_time", {}, NOW)


def test_xml_has_catch_up_and_right_trigger():
    t = build_task("weekdays", "08:30", "get_time", {}, NOW)
    xml = task_xml(t, r"C:\v\pythonw.exe", f"-m assistant.run_task {t.id}", r"C:\proj")
    assert "<StartWhenAvailable>true</StartWhenAvailable>" in xml
    assert "<Monday />" in xml and "<Friday />" in xml and "<Saturday />" not in xml
    assert f"<StartBoundary>{t.date}T08:30:00</StartBoundary>" in xml
    assert "InteractiveToken" in xml and "LeastPrivilege" in xml
    once = build_task("once", "20:00", "get_time", {}, NOW, date_text="today")
    assert "<TimeTrigger>" in task_xml(once, "p", "a", "w")


def test_xml_escapes_description():
    t = build_task("daily", "09:00", "get_time", {}, NOW, action_text="say <hi> & 'bye'")
    xml = task_xml(t, "p", "a", "w")
    assert "&lt;hi&gt; &amp;" in xml


def test_storage_round_trip(tmp_path):
    t = build_task("daily", "09:00", "send_whatsapp", {"contact": "Ali Khan", "message": "صبح بخیر"}, NOW)
    path = tmp_path / "schedules.yaml"
    save_tasks(path, [t])
    assert load_tasks(path) == [t]
    assert load_tasks(tmp_path / "none.yaml") == []


def test_windows_scheduler_uses_argument_lists():
    calls = []

    def fake_run(args):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)
    t = build_task("daily", "09:00", "get_time", {}, NOW)
    s = WindowsScheduler(runner=fake_run, python=r"C:\v\pythonw.exe")
    assert s.create(t) and s.delete(t) and s.exists(t)
    assert calls[0][:4] == ["schtasks", "/Create", "/TN", f"VisionX\\{t.id}"] and "/XML" in calls[0]
    assert calls[1] == ["schtasks", "/Delete", "/TN", f"VisionX\\{t.id}", "/F"]


# --- skills end to end -------------------------------------------------------------------------
class FakeScheduler:
    def __init__(self, ok=True):
        self.ok, self.created, self.deleted = ok, [], []

    def create(self, t):
        self.created.append(t.id)
        return self.ok

    def delete(self, t):
        self.deleted.append(t.id)
        return True

    def exists(self, t):
        return t.id in self.created


class RoutingBrain:
    """Top-level decisions in order; inner commands for schedule_task routed by `inner`."""

    def __init__(self, decisions, inner=None):
        self.decisions, self.inner, self.inputs = list(decisions), inner or {}, []

    def decide(self, command):
        self.inputs.append(command)
        if command in self.inner:
            return self.inner[command]
        return self.decisions.pop(0)


class FakeIO:
    def __init__(self, answers=()):
        self.said, self.asked, self.answers = [], [], list(answers)

    def say(self, t):
        self.said.append(t)

    def note(self, t):
        pass

    def ask(self, q):
        self.asked.append(q)
        return self.answers.pop(0)


@pytest.fixture
def env(config, tmp_path, monkeypatch):
    sched = FakeScheduler()
    config.settings["scheduler"] = {"file": str(tmp_path / "schedules.yaml"), "announce": True}
    monkeypatch.setattr("assistant.skills._schedules.make_scheduler", lambda: sched)
    monkeypatch.setattr("assistant.skills._schedules.now", lambda: NOW)
    return config, tmp_path, sched


def session(config, tmp_path, brain, io):
    reg = discover(config)
    reg.attach(brain)
    return Session(io, brain, reg, ActionLogger(tmp_path / "a.jsonl"), show_timings=False)


GM = Decision(skill="schedule_task", params={"command": "Ali Khan ko good morning bhejo",
                                              "time": "09:00", "repeat": "daily"})
GM_INNER = {"Ali Khan ko good morning bhejo":
            Decision(skill="send_whatsapp", params={"contact": "Ali Khan", "message": "good morning"})}


def test_schedule_whatsapp_daily_reads_back_and_saves(env):
    config, tmp_path, sched = env
    io = FakeIO(["haan"])
    s = session(config, tmp_path, RoutingBrain([GM], GM_INNER), io)
    out = s.step("har roz subah 9 baje Ali Khan ko good morning bhejo")
    assert io.asked == ["Every day at 9:00 AM: send 'good morning' to Ali Khan (+92 300 1234567) "
                        "on WhatsApp. Schedule it? (yes/no)"]
    tasks = load_tasks(tmp_path / "schedules.yaml")
    assert len(tasks) == 1 and tasks[0].skill == "send_whatsapp"
    assert tasks[0].params == {"contact": "Ali Khan", "message": "good morning"}
    assert sched.created == [tasks[0].id] and out.reply.startswith("Scheduled: every day at 9:00 AM")


def test_schedule_no_means_nothing_saved(env):
    config, tmp_path, sched = env
    s = session(config, tmp_path, RoutingBrain([GM], GM_INNER), FakeIO(["nahi"]))
    s.step("x")
    assert load_tasks(tmp_path / "schedules.yaml") == [] and sched.created == []


def test_schedule_asks_about_unknown_contact_first(env):
    config, tmp_path, sched = env
    d = Decision(skill="schedule_task", params={"command": "Bilal ko hi bhejo", "time": "09:00", "repeat": "daily"})
    inner = {"Bilal ko hi bhejo": Decision(skill="send_whatsapp", params={"contact": "Bilal", "message": "hi"})}
    io = FakeIO()
    s = session(config, tmp_path, RoutingBrain([d], inner), io)
    out = s.step("x")
    assert "contacts.yaml" in out.reply and io.asked == [] and sched.created == []


def test_cannot_schedule_scheduling(env):
    config, tmp_path, _ = env
    d = Decision(skill="schedule_task", params={"command": "schedule something", "time": "09:00", "repeat": "daily"})
    inner = {"schedule something": Decision(skill="list_scheduled_tasks", params={})}
    out = session(config, tmp_path, RoutingBrain([d], inner), FakeIO()).step("x")
    assert "can't schedule scheduling" in out.reply


def test_windows_refusal_rolls_back(env):
    config, tmp_path, sched = env
    sched.ok = False
    out = session(config, tmp_path, RoutingBrain([GM], GM_INNER), FakeIO(["yes"])).step("x")
    assert "didn't accept" in out.reply and load_tasks(tmp_path / "schedules.yaml") == []


def test_list_and_delete(env):
    config, tmp_path, sched = env
    s = session(config, tmp_path, RoutingBrain([GM], GM_INNER), FakeIO(["yes"]))
    s.step("x")
    t2 = build_task("weekdays", "20:30", "open_website", {"target": "youtube"}, NOW,
                    action_text="open youtube")
    save_tasks(tmp_path / "schedules.yaml", load_tasks(tmp_path / "schedules.yaml") + [t2])
    sched.created.append(t2.id)

    io = FakeIO(["ji"])
    brain = RoutingBrain([Decision(skill="list_scheduled_tasks"),
                          Decision(skill="delete_scheduled_task", params={"which": "9 baje"})])
    s = session(config, tmp_path, brain, io)
    listing = s.step("mere scheduled tasks batao").reply
    assert listing.startswith("You have 2 scheduled tasks: 1) Every day at 9:00 AM") and "2) Every weekday at 8:30 PM" in listing
    s.step("9 baje wala task delete karo")
    assert io.asked[0].startswith("Delete the scheduled task 'Every day at 9:00 AM")
    left = load_tasks(tmp_path / "schedules.yaml")
    assert [t.id for t in left] == [t2.id] and len(sched.deleted) == 1


def test_delete_asks_when_ambiguous(env):
    config, tmp_path, _ = env
    a = build_task("daily", "09:00", "get_time", {}, NOW, action_text="tell the time")
    b = build_task("daily", "21:00", "get_time", {}, NOW, action_text="tell the time")
    save_tasks(tmp_path / "schedules.yaml", [a, b])
    out = session(config, tmp_path, RoutingBrain([Decision(skill="delete_scheduled_task",
                                                           params={"which": "9 baje"})]), FakeIO()).step("x")
    assert out.reply.startswith("Which task do you mean: 1) Every day at 9:00 AM")


# --- run_task (what Windows runs) -----------------------------------------------------------------
def test_run_task_runs_stored_action_without_asking(env):
    config, tmp_path, sched = env
    t = build_task("daily", "09:00", "send_whatsapp", {"contact": "Ali Khan", "message": "good morning"}, NOW,
                   action_text="send 'good morning' to Ali Khan")
    save_tasks(tmp_path / "schedules.yaml", [t])
    config.settings["whatsapp"] = {"auto_send": True}
    spoken = []
    with patch("assistant.skills._whatsapp.launch") as launch, \
         patch("assistant.skills._whatsapp.send_verified", return_value="sent") as send:
        result = runner.run(t.id, config, ActionLogger(tmp_path / "a.jsonl"), spoken.append)
    launch.assert_called_once_with("whatsapp://send?phone=923001234567&text=good%20morning")
    assert send.call_args.kwargs["timeout"] == 30                  # longer for a cold WhatsApp start
    assert result.ok and spoken == ["Scheduled task: Sent your message to Ali Khan."]
    log = json.loads((tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert log["scheduled"] is True and log["task_id"] == t.id and log["confirmed"] is True
    assert load_tasks(tmp_path / "schedules.yaml") == [t]           # daily task stays


def test_run_task_removes_one_time_task(env):
    config, tmp_path, sched = env
    t = build_task("once", "20:00", "get_time", {}, NOW, date_text="today")
    save_tasks(tmp_path / "schedules.yaml", [t])
    result = runner.run(t.id, config, ActionLogger(tmp_path / "a.jsonl"))
    assert result.ok and load_tasks(tmp_path / "schedules.yaml") == [] and sched.deleted == [t.id]


def test_run_task_unknown_id_cleans_up(env):
    config, tmp_path, sched = env
    result = runner.run("ffffff", config, ActionLogger(tmp_path / "a.jsonl"))
    assert not result.ok and sched.deleted == ["ffffff"]


def test_run_task_never_runs_scheduling_skills(env):
    config, tmp_path, _ = env
    t = build_task("daily", "09:00", "delete_scheduled_task", {"which": "1"}, NOW)
    save_tasks(tmp_path / "schedules.yaml", [t])
    result = runner.run(t.id, config, ActionLogger(tmp_path / "a.jsonl"))
    assert not result.ok and load_tasks(tmp_path / "schedules.yaml") == [t]
