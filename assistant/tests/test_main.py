import json

from assistant.core.brain import Decision
from assistant.core.logger import ActionLogger
from assistant.core.registry import Registry
from assistant.main import handle
from assistant.skills.base import Result, Skill


class FakeBrain:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, command):
        return self.decision


class FakeIO:
    def __init__(self, answers=()):
        self.said, self.asked, self.answers = [], [], list(answers)

    def say(self, text):
        self.said.append(text)

    def ask(self, q):
        self.asked.append(q)
        return self.answers.pop(0)


class RiskySkill(Skill):
    name = "risky"
    description = "A risky thing."
    parameters = {"type": "object", "properties": {"to": {"type": "string"}}, "required": ["to"]}
    risk = "confirm"
    ran = False

    def confirm_prompt(self, to, **_):
        return f"Do the risky thing to {to}?"

    def run(self, to, **_):
        RiskySkill.ran = True
        return Result(True, f"Done for {to}.")


class SafeSkill(Skill):
    name = "safe"
    description = "A safe thing."

    def run(self, **_):
        return Result(True, "Safe done.")


class BrokenSkill(Skill):
    name = "broken"
    description = "Crashes."

    def run(self, **_):
        raise RuntimeError("boom")


def setup(config, tmp_path, decision, answers=()):
    RiskySkill.ran = False
    registry = Registry([RiskySkill(config), SafeSkill(config), BrokenSkill(config)])
    log_path = tmp_path / "actions.jsonl"
    return FakeBrain(decision), registry, FakeIO(answers), ActionLogger(log_path), log_path


def last_log(path):
    return json.loads(path.read_text(encoding="utf-8").splitlines()[-1])


def test_safe_skill_runs_without_confirmation(config, tmp_path):
    brain, reg, io, logger, path = setup(config, tmp_path, Decision(skill="safe"))
    assert handle("do it", brain, reg, io, logger) == "Safe done."
    assert io.asked == []
    assert last_log(path)["confirmed"] is None and last_log(path)["skill"] == "safe"


def test_confirm_skill_runs_on_haan(config, tmp_path):
    brain, reg, io, logger, path = setup(config, tmp_path, Decision(skill="risky", params={"to": "Ali"}), ["haan"])
    assert handle("x", brain, reg, io, logger) == "Done for Ali."
    assert io.asked == ["Do the risky thing to Ali? (yes/no)"]
    assert RiskySkill.ran and last_log(path)["confirmed"] is True


def test_confirm_skill_cancels_on_anything_else(config, tmp_path):
    brain, reg, io, logger, path = setup(config, tmp_path, Decision(skill="risky", params={"to": "Ali"}), ["ok"])
    assert handle("x", brain, reg, io, logger) == "Okay, cancelled."
    assert not RiskySkill.ran
    log = last_log(path)
    assert log["confirmed"] is False and log["ok"] is False


def test_missing_required_param_asks(config, tmp_path):
    brain, reg, io, logger, _ = setup(config, tmp_path, Decision(skill="risky", params={}))
    reply = handle("x", brain, reg, io, logger)
    assert "to" in reply and not RiskySkill.ran and io.asked == []


def test_plain_reply_is_shown_and_logged(config, tmp_path):
    brain, reg, io, logger, path = setup(config, tmp_path, Decision(reply="Kaunsi app?"))
    assert handle("kholo", brain, reg, io, logger) == "Kaunsi app?"
    assert io.said == ["Kaunsi app?"] and last_log(path)["skill"] is None


def test_broken_skill_does_not_crash(config, tmp_path):
    brain, reg, io, logger, path = setup(config, tmp_path, Decision(skill="broken"))
    reply = handle("x", brain, reg, io, logger)
    assert "went wrong" in reply and last_log(path)["ok"] is False
