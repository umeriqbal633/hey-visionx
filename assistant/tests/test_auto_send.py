from unittest.mock import patch

from assistant.skills import _whatsapp as w
from assistant.skills.send_whatsapp import SendWhatsApp


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class FakeBox:
    """Message box: shows `values` over time; Send/Enter clears it if `clears`.
    `has_button`: whether WhatsApp's Send button can be found and clicked."""

    def __init__(self, values, clears=True, has_button=True):
        self.values, self.clears, self.has_button = list(values), clears, has_button
        self.focused = self.entered = self.clicked = False

    def value(self):
        if self.entered and self.clears:
            return ""
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]

    def focus(self):
        self.focused = True

    def click_send(self):
        if not self.has_button:
            return False
        self.clicked = self.entered = True
        return True


def run(message, box, foregrounds=("whatsapp.root.exe",), find=None):
    seq, pressed, clock = list(foregrounds), [], Clock()

    def fg():
        return seq.pop(0) if len(seq) > 1 else seq[0]

    def press():
        pressed.append(1)
        if box is not None:
            box.entered = True
    status = w.send_verified(message, timeout=10, foreground=fg, find_box=find or (lambda: box),
                             press=press, sleep=clock.sleep, clock=clock.now)
    return status, pressed


def test_clicks_send_when_box_holds_exactly_the_message_and_clears():
    box = FakeBox(["", "main late", "main late hoon"])
    status, pressed = run("main late hoon", box)
    assert status == w.SENT and box.clicked and pressed == []


def test_send_button_works_even_if_whatsapp_not_in_front():
    # What happened at 11:28: Windows kept the terminal in front.
    box = FakeBox(["main late hoon"])
    status, pressed = run("main late hoon", box, foregrounds=("windowsterminal.exe",))
    assert status == w.SENT and box.clicked


def test_enter_fallback_only_without_button_and_with_whatsapp_in_front():
    box = FakeBox(["main late hoon"], has_button=False)
    status, pressed = run("main late hoon", box)
    assert status == w.SENT and pressed == [1] and box.focused
    box = FakeBox(["main late hoon"], has_button=False)
    status, pressed = run("main late hoon", box, foregrounds=("chrome.exe",))
    assert status == w.NOT_FRONT and pressed == []


def test_old_draft_in_box_blocks_sending():
    # What actually happened: an old unsent draft plus the new message, joined together.
    box = FakeBox(["Hey Saad, how are you? main late hoon"])
    status, pressed = run("main late hoon", box)
    assert status == w.DRAFT_CONFLICT and not box.clicked and pressed == []


def test_send_not_taken_is_not_reported_as_sent():
    box = FakeBox(["main late hoon"], clears=False)
    status, _ = run("main late hoon", box)
    assert status == w.NOT_CLEARED and box.clicked


def test_message_never_appears_means_no_enter():
    box = FakeBox([""])
    status, pressed = run("main late hoon", box)
    assert status == w.NO_TEXT and pressed == []


def test_box_not_found_means_no_enter():
    status, pressed = run("hi", None, find=lambda: None)
    assert status == w.NO_TEXT and pressed == []


def test_whitespace_differences_are_ok():
    assert w.same_text("main  late\nhoon ", "main late hoon")
    assert not w.same_text("x main late hoon", "main late hoon")


def skill_run(config, status):
    config.settings["whatsapp"] = {"auto_send": True}
    with patch("assistant.skills._whatsapp.launch"), \
         patch("assistant.skills._whatsapp.send_verified", return_value=status) as send:
        result = SendWhatsApp(config).run(contact="Ali Khan", message=" main late hoon ")
    return result, send


def test_skill_reports_sent_only_when_verified(config):
    result, send = skill_run(config, w.SENT)
    assert send.call_args.args[0] == "main late hoon"
    assert result.ok and result.reply == "Sent your message to Ali Khan."


def test_skill_reports_draft_conflict(config):
    result, _ = skill_run(config, w.DRAFT_CONFLICT)
    assert not result.ok and "already had unsent text" in result.reply


def test_skill_reports_not_sent(config):
    for status in (w.NOT_FRONT, w.NO_TEXT, w.NOT_CLEARED):
        result, _ = skill_run(config, status)
        assert not result.ok and "typed but not sent" in result.reply


def test_skill_auto_send_off_only_types(config):
    config.settings["whatsapp"] = {"auto_send": False}
    with patch("assistant.skills._whatsapp.launch"), \
         patch("assistant.skills._whatsapp.send_verified") as send:
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
         patch("assistant.skills._whatsapp.send_verified") as send:
        handle("x", Brain(), discover(config), IO(), ActionLogger(tmp_path / "a.jsonl"))
    launch.assert_not_called()
    send.assert_not_called()
