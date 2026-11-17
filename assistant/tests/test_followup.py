import json

from assistant.core.brain import Decision
from assistant.core.logger import ActionLogger
from assistant.core.registry import discover
from assistant.core.timing import Timings
from assistant.main import EXIT_WORDS, Session, main, with_follow_up


class ScriptedBrain:
    """Returns decisions in order and records what it was asked."""

    def __init__(self, *decisions):
        self.decisions = list(decisions)
        self.inputs = []

    def decide(self, command):
        self.inputs.append(command)
        return self.decisions.pop(0)


class FakeIO:
    def __init__(self, answers=()):
        self.said, self.notes, self.answers = [], [], list(answers)

    def say(self, t):
        self.said.append(t)

    def note(self, t):
        self.notes.append(t)

    def ask(self, q):
        self.said.append(q)
        return self.answers.pop(0)


def session(config, tmp_path, brain, io):
    return Session(io, brain, discover(config), ActionLogger(tmp_path / "a.jsonl"))


def test_answer_is_sent_with_original_command(config, tmp_path):
    brain = ScriptedBrain(
        Decision(skill="send_whatsapp", params={"contact": "Ali", "message": "main late hoon"}),
        Decision(skill="send_whatsapp", params={"contact": "Ali Raza", "message": "main late hoon"}),
    )
    io = FakeIO(answers=["no"])
    s = session(config, tmp_path, brain, io)
    first = s.step("Ali ko message bhejo ke main late hoon")
    assert first.reply == "Which Ali do you mean: Ali Khan or Ali Raza?" and s.pending
    s.step("Ali Raza")
    assert brain.inputs[1] == with_follow_up("Ali ko message bhejo ke main late hoon",
                                             "Which Ali do you mean: Ali Khan or Ali Raza?", "Ali Raza")
    assert "Send 'main late hoon' to Ali Raza (+92 333 7654321)? (yes/no)" in io.said
    assert s.pending is None


def test_did_you_mean_yes_runs_suggestion_without_brain(config, tmp_path):
    """'Did you mean Ali Khan?' answered 'G.' (a spoken ji) opens Ali Khan's chat directly."""
    from unittest.mock import patch
    brain = ScriptedBrain(Decision(skill="open_whatsapp_chat", params={"contact": "Ali Kaan"}))
    io = FakeIO()
    io.extra_yes = frozenset({"g"})
    config.contacts = [c for c in config.contacts if c.name != "Ali Raza"]
    s = session(config, tmp_path, brain, io)
    assert s.step("Ali Kaan ki chat kholo").reply == "Did you mean Ali Khan?"
    with patch("assistant.skills._whatsapp.launch") as launch:
        outcome = s.step("G.")
    launch.assert_called_once_with("whatsapp://send?phone=923001234567")
    assert outcome.reply == "Opening your WhatsApp chat with Ali Khan."
    assert len(brain.inputs) == 1                     # the brain wasn't asked again
    log = json.loads((tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert log["follow_up"] is True and log["params"]["contact"] == "Ali Khan"


def test_did_you_mean_no_goes_back_to_brain(config, tmp_path):
    brain = ScriptedBrain(Decision(skill="open_whatsapp_chat", params={"contact": "Ali Kaan"}),
                          Decision(reply="Kis se baat karni hai?"))
    config.contacts = [c for c in config.contacts if c.name != "Ali Raza"]
    s = session(config, tmp_path, brain, FakeIO())
    s.step("Ali Kaan ki chat kholo")
    s.step("nahi, Sara")
    assert len(brain.inputs) == 2 and 'The user answered: "nahi, Sara"' in brain.inputs[1]


def test_did_you_mean_yes_still_needs_read_back_for_risky(config, tmp_path):
    """A suggested contact for a WhatsApp send still goes through the normal yes/no read-back."""
    from unittest.mock import patch
    brain = ScriptedBrain(Decision(skill="send_whatsapp", params={"contact": "Ali Kaan", "message": "hi"}))
    io = FakeIO(answers=["no"])
    config.contacts = [c for c in config.contacts if c.name != "Ali Raza"]
    s = session(config, tmp_path, brain, io)
    s.step("Ali Kaan ko hi bhejo")
    with patch("assistant.skills._whatsapp.launch") as launch:
        s.step("yes")
    assert "Send 'hi' to Ali Khan (+92 300 1234567)? (yes/no)" in io.said
    launch.assert_not_called()


def test_brain_question_also_takes_follow_up(config, tmp_path):
    brain = ScriptedBrain(Decision(reply="Kis app ko kholna hai?"),
                          Decision(skill="get_time"))
    s = session(config, tmp_path, brain, FakeIO())
    s.step("kholo")
    s.step("chrome")
    assert brain.inputs[1].startswith("kholo\n(You asked:") and '"chrome"' in brain.inputs[1]


def test_only_one_follow_up(config, tmp_path):
    brain = ScriptedBrain(Decision(reply="Which app?"), Decision(reply="Which one exactly?"),
                          Decision(skill="get_time"))
    s = session(config, tmp_path, brain, FakeIO())
    s.step("kholo")
    s.step("woh wali")
    assert s.pending is None                 # second question not chained
    s.step("time kya hua hai")
    assert brain.inputs[2] == "time kya hua hai"


def test_statements_do_not_create_follow_up(config, tmp_path):
    brain = ScriptedBrain(Decision(skill="get_time"), Decision(skill="get_time"))
    s = session(config, tmp_path, brain, FakeIO())
    s.step("time kya hua hai")
    assert s.pending is None


def test_timings_logged_and_shown(config, tmp_path):
    brain = ScriptedBrain(Decision(skill="get_time"))
    io = FakeIO()
    s = session(config, tmp_path, brain, io)
    t = Timings()
    t.add("rec", 1.0)
    t.add("stt", 0.4)
    s.step("time kya hua hai", t)
    log = json.loads((tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert {"rec", "stt", "brain", "skill", "release_to_action"} <= set(log["timings"])
    assert io.notes and io.notes[-1].startswith("⏱") and "release→action" in io.notes[-1]


def test_exit_words_match_spoken_punctuation():
    from assistant.core.matching import normalize
    assert normalize("Exit.") in EXIT_WORDS and normalize("Band karo!") in EXIT_WORDS


def test_text_flag_selects_text_mode(monkeypatch):
    called = {}
    monkeypatch.setattr("assistant.main.build_voice_io", lambda c: called.setdefault("voice", True))
    monkeypatch.setattr("assistant.main.get_provider", lambda c: object())
    monkeypatch.setattr("assistant.main.Session.run", lambda self: 0)
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    assert main(["--text"]) == 0 and "voice" not in called


def test_voice_mode_failure_suggests_text(monkeypatch, capsys):
    def boom(c):
        raise OSError("no microphone")
    monkeypatch.setattr("assistant.main.build_voice_io", boom)
    monkeypatch.setattr("assistant.main.get_provider", lambda c: object())
    assert main([]) == 1
    assert "--text" in capsys.readouterr().out
