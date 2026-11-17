from unittest.mock import patch

from assistant.skills._whatsapp import send_when_ready
from assistant.skills.send_whatsapp import SendWhatsApp


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(foregrounds, timeout=10.0):
    """foregrounds: successive results of foreground(); the last one repeats."""
    seq, pressed, clock = list(foregrounds), [], Clock()

    def fg():
        return seq.pop(0) if len(seq) > 1 else seq[0]
    ok = send_when_ready(timeout=timeout, settle=2.0, foreground=fg, press=lambda: pressed.append(1),
                         sleep=clock.sleep, clock=clock.now)
    return ok, pressed


def test_presses_enter_when_whatsapp_is_in_front():
    ok, pressed = run(["windowsterminal.exe", "windowsterminal.exe", "whatsapp.root.exe"])
    assert ok and pressed == [1]


def test_never_presses_if_whatsapp_never_comes_to_front():
    ok, pressed = run(["chrome.exe"])
    assert not ok and pressed == []


def test_never_presses_if_user_switches_away_while_loading():
    ok, pressed = run(["whatsapp.root.exe", "chrome.exe"])
    assert not ok and pressed == []


def test_unknown_foreground_is_not_whatsapp():
    ok, pressed = run([""])
    assert not ok and pressed == []


def test_skill_auto_send_on(config):
    config.settings["whatsapp"] = {"auto_send": True}
    with patch("assistant.skills._whatsapp.launch") as launch, \
         patch("assistant.skills._whatsapp.send_when_ready", return_value=True) as send:
        result = SendWhatsApp(config).run(contact="Ali Khan", message="main late hoon")
    launch.assert_called_once()
    send.assert_called_once()
    assert result.ok and result.reply == "Sent your message to Ali Khan."


def test_skill_auto_send_window_problem_is_reported(config):
    config.settings["whatsapp"] = {"auto_send": True}
    with patch("assistant.skills._whatsapp.launch"), \
         patch("assistant.skills._whatsapp.send_when_ready", return_value=False):
        result = SendWhatsApp(config).run(contact="Ali Khan", message="hi")
    assert not result.ok and "typed but not sent" in result.reply


def test_skill_auto_send_off_only_types(config):
    config.settings["whatsapp"] = {"auto_send": False}
    with patch("assistant.skills._whatsapp.launch"), \
         patch("assistant.skills._whatsapp.send_when_ready") as send:
        result = SendWhatsApp(config).run(contact="Ali Khan", message="hi")
    send.assert_not_called()
    assert "press Enter" in result.reply


def test_no_auto_send_without_yes(config, tmp_path):
    """The read-back still comes first: a 'no' means WhatsApp is never even opened."""
    from assistant.core.brain import Decision
    from assistant.core.logger import ActionLogger
    from assistant.core.registry import discover
    from assistant.main import handle

    class Brain:
        def decide(self, _):
            return Decision(skill="send_whatsapp", params={"contact": "Ali Khan", "message": "hi"})

    class IO:
        def say(self, t):
            pass

        def ask(self, q):
            return "no"

    config.settings["whatsapp"] = {"auto_send": True}
    with patch("assistant.skills._whatsapp.launch") as launch, \
         patch("assistant.skills._whatsapp.send_when_ready") as send:
        handle("x", Brain(), discover(config), IO(), ActionLogger(tmp_path / "a.jsonl"))
    launch.assert_not_called() and send.assert_not_called()
