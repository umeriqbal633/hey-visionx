from unittest.mock import patch

import pytest

from assistant.core.brain import Decision
from assistant.core.groups import find_groups, load_groups, resolve_group, suggested_group
from assistant.core.schedules import load_tasks
from assistant.skills import _whatsapp as w
from assistant.skills.base import Ask
from assistant.skills.send_whatsapp import SendWhatsApp
from assistant.skills.send_whatsapp_group import SendWhatsAppGroup
from assistant.tests.test_schedules import FakeIO, RoutingBrain, session

GROUP = "Class C10 (8 PM)"
SEND = "assistant.skills._whatsapp.send_to_group"


# --- groups.yaml lookup ------------------------------------------------------------------------
def test_lookup_by_name_or_alias(config):
    assert resolve_group(config.groups, "c10")[0].name == GROUP
    assert resolve_group(config.groups, "class c10 (8 pm)")[0].name == GROUP
    assert resolve_group(config.groups, "Family")[0].name == "Family Group 🏠"


def test_unknown_group_asks_never_guesses(config):
    found, q = resolve_group(config.groups, "cricket")
    assert found is None and "groups.yaml" in q
    assert suggested_group(config.groups, "c10") is None            # exact: nothing to suggest


def test_close_name_is_only_suggested(config):
    found, q = resolve_group(config.groups, "famly")
    assert found is None and q == "Did you mean the group Family Group 🏠?"


def test_no_groups_file(tmp_path):
    assert load_groups(tmp_path / "groups.yaml") is None
    assert "groups.example.yaml" in resolve_group(None, "c10")[1]


def test_groups_file_keeps_names_as_text(tmp_path):
    p = tmp_path / "groups.yaml"
    p.write_text("groups:\n  - name: Class C10 (8 PM)\n    aliases: [c10, 2024]\n", encoding="utf-8")
    g = load_groups(p)
    assert g[0].name == "Class C10 (8 PM)" and g[0].aliases == ("c10", "2024")


# --- matching WhatsApp's screen ----------------------------------------------------------------
@pytest.mark.parametrize("title, ok", [
    ("Class C10 (8 PM) 8:21 pm", True),
    ("2 unread messages Class C10 (8 PM) 8:21 pm", True),
    ("1 unread message Class C10 (8 PM)", True),
    ("Class C1 (6 PM) 8:21 pm", False),
    ("Class C10 (8 PM) Extra 8:21 pm", True),     # the chat-name check after opening decides
    ("Old Class C10 (8 PM) 8:21 pm", False),
])
def test_result_matches(title, ok):
    assert w.result_matches(title, GROUP) is ok


def test_c1_does_not_match_c10():
    assert not w.result_matches("Class C10 (8 PM) 8:21 pm", "Class C1")


def test_is_group_chat_is_exact():
    assert w.is_group_chat("Type a message to group Class C10 (8 PM)", GROUP)
    assert w.is_group_chat("Type a message to group Class\xa0C10 (8 PM)", GROUP)
    assert not w.is_group_chat("Type a message to Class C10 (8 PM)", GROUP)          # a person
    assert not w.is_group_chat("Type a message to group Class C10 (8 PM) old", GROUP)
    assert not w.is_group_chat("Type a message to group Class C1 (6 PM)", GROUP)


# --- the send procedure against a fake WhatsApp ------------------------------------------------
class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class Box:
    def __init__(self, chat, text=""):
        self.chat, self.text, self.sent = chat, text, []

    def name(self):
        return f"Type a message to group {self.chat}" if self.chat else "Type a message to Saad"

    def value(self):
        return self.text

    clickable = True              # False = another window covers the box

    def focus(self):
        pass

    def click_into(self):
        return self.clickable

    def click_send(self):
        self.sent.append(self.text)
        self.text = ""
        return True


class FakeWhatsApp:
    """Search results by query; opening a result switches the open chat to `opens` (default:
    the result's group). `drafts` = unsent text already in a chat."""

    def __init__(self, open_chat="", results=(), opens=None, drafts=None, action_works=True):
        self.open_chat, self.result_titles, self.opens = open_chat, list(results), opens
        self.drafts, self.action_works = dict(drafts or {}), action_works
        self.searched, self.typed, self.boxes, self.cleared = [], [], {}, False

    def compose(self):
        if self.open_chat not in self.boxes:
            self.boxes[self.open_chat] = Box(self.open_chat, self.drafts.get(self.open_chat, ""))
        return self.boxes[self.open_chat]

    def search(self, text):
        self.searched.append(text)
        return True

    def results(self):
        return self.result_titles if self.searched else []

    def open_result(self, title, click=False):
        if click or self.action_works:
            self.open_chat = self.opens if self.opens is not None else GROUP
        return True

    def type_text(self, text):
        self.typed.append((self.open_chat, text))
        self.compose().text += text

    def clear_search(self):
        self.cleared = True

    def bring_to_front(self):
        pass


def send(app, message="class 8 baje hai", front=("whatsapp.root.exe",), send_it=True):
    clock, opened = Clock(), []
    fg = list(front)
    status = w.send_to_group(GROUP, message, send=send_it, timeout=5,
                             open_app=lambda: opened.append(1), window=lambda: app,
                             foreground=lambda: fg.pop(0) if len(fg) > 1 else fg[0],
                             sleep=clock.sleep, clock=clock.now)
    return status, opened


def test_searches_opens_exact_group_types_and_sends():
    app = FakeWhatsApp(open_chat="Saad", results=["Class C1 (6 PM) 7:00 pm", "2 unread messages Class C10 (8 PM) 8:21 pm"])
    status, opened = send(app)
    assert status == w.SENT and opened == [1]
    assert app.searched == [GROUP]
    assert app.typed == [(GROUP, "class 8 baje hai")]
    assert app.boxes[GROUP].sent == ["class 8 baje hai"]


def test_already_open_group_skips_search():
    app = FakeWhatsApp(open_chat=GROUP)
    status, _ = send(app)
    assert status == w.SENT and app.searched == []


def test_falls_back_to_a_click_when_the_accessibility_action_does_nothing():
    app = FakeWhatsApp(open_chat="Saad", results=["Class C10 (8 PM)"], action_works=False)
    assert send(app)[0] == w.SENT


def test_group_not_in_results_types_nothing():
    app = FakeWhatsApp(open_chat="Saad", results=["Class C1 (6 PM) 7:00 pm"])
    status, _ = send(app)
    assert status == w.NOT_FOUND and app.typed == [] and app.cleared


def test_wrong_chat_opened_types_nothing():
    # The result looked right, but WhatsApp opened something else: never type there.
    app = FakeWhatsApp(open_chat="Saad", results=["Class C10 (8 PM)"], opens="Class C10 (8 PM) old")
    status, _ = send(app)
    assert status == w.WRONG_CHAT and app.typed == []


def test_unsent_draft_in_group_blocks_sending():
    app = FakeWhatsApp(open_chat=GROUP, drafts={GROUP: "half written note"})
    status, _ = send(app)
    assert status == w.DRAFT_CONFLICT and app.typed == [] and app.boxes[GROUP].sent == []


def test_whatsapp_not_in_front_after_the_click_types_nothing():
    # Search and opening work without the keyboard; typing needs WhatsApp in front.
    app = FakeWhatsApp(open_chat="Saad", results=["Class C10 (8 PM)"])
    status, _ = send(app, front=("chrome.exe",))
    assert status == w.NOT_FRONT and app.typed == []


def test_covered_box_is_never_clicked_or_typed_into():
    app = FakeWhatsApp(open_chat=GROUP)
    app.compose().clickable = False
    status, _ = send(app)
    assert status == w.NOT_FRONT and app.typed == []


def test_lines_are_kept_and_spaces_tidied():
    # type_text turns each new line into Shift+Enter, so the layout survives without an early send.
    app = FakeWhatsApp(open_chat=GROUP)
    status, _ = send(app, message="@all  \nDear students,\n\nLink:  https://x.y/z\r\n")
    assert app.typed == [(GROUP, "@all\nDear students,\n\nLink: https://x.y/z")]
    assert status == w.SENT


def test_same_text_ignores_how_lines_are_stored():
    assert w.same_text("@all\nDear students,", "@all Dear students,")
    assert w.same_text("a\r\n\nb", "a b")
    assert not w.same_text("a b", "a c")


def test_auto_send_off_only_types():
    app = FakeWhatsApp(open_chat=GROUP)
    status, _ = send(app, send_it=False)
    assert status == w.TYPED and app.boxes[GROUP].sent == []


# --- the skill ---------------------------------------------------------------------------------
def test_is_a_confirm_skill_with_exact_read_back(config):
    skill = SendWhatsAppGroup(config)
    assert skill.risk == "confirm"
    assert skill.confirm_prompt(group="c10", message="class 8 baje hai") == \
        "Send 'class 8 baje hai' to the WhatsApp group Class C10 (8 PM)?"


def test_check_unknown_and_suggestion(config):
    skill = SendWhatsAppGroup(config)
    assert "groups.yaml" in skill.check(group="cricket", message="hi")
    ask = skill.check(group="famly", message="hi")
    assert isinstance(ask, Ask) and ask.on_yes == {"group": "Family Group 🏠"}
    assert skill.check(group="c10", message="hi") is None
    assert skill.check(group="c10", message=" ") == "What should I send to the group?"


@pytest.mark.parametrize("status, ok, words", [
    (w.SENT, True, "Sent your message to the group Class C10 (8 PM)."),
    (w.NOT_FOUND, False, "couldn't find the group"),
    (w.WRONG_CHAT, False, "didn't type anything"),
    (w.DRAFT_CONFLICT, False, "already had unsent text"),
    (w.NOT_FRONT, False, "didn't come to the front"),
])
def test_run_replies(config, status, ok, words):
    config.settings["whatsapp"] = {"auto_send": True}
    with patch(SEND, return_value=status) as s:
        result = SendWhatsAppGroup(config).run(group="c10", message="class 8 baje hai")
    s.assert_called_once()
    assert s.call_args.args == ("Class C10 (8 PM)", "class 8 baje hai") and s.call_args.kwargs["send"]
    assert result.ok is ok and words in result.reply and result.reply[0].isupper()


def test_auto_send_off_passes_send_false(config):
    config.settings["whatsapp"] = {"auto_send": False}
    with patch(SEND, return_value=w.TYPED) as s:
        result = SendWhatsAppGroup(config).run(group="c10", message="hi")
    assert s.call_args.kwargs["send"] is False and "press Enter" in result.reply


def test_unknown_group_never_touches_whatsapp(config):
    with patch(SEND) as s:
        result = SendWhatsAppGroup(config).run(group="cricket", message="hi")
    s.assert_not_called()
    assert not result.ok


def test_person_skill_points_to_a_group_name(config):
    q = SendWhatsApp(config).check(contact="c10", message="hi")
    assert q == "Class C10 (8 PM) is a WhatsApp group; should I send it to the group?"
    assert find_groups(config.groups, "Ali Khan") == []
    assert SendWhatsApp(config).check(contact="Ali Khan", message="hi") is None


# --- through the main loop and the scheduler ----------------------------------------------------
def test_yes_sends_no_cancels(config, tmp_path):
    d = Decision(skill="send_whatsapp_group", params={"group": "c10", "message": "class 8 baje hai"})
    config.settings["whatsapp"] = {"auto_send": True}
    for answer, called in (("haan", True), ("nahi", False)):
        io = FakeIO([answer])
        with patch(SEND, return_value=w.SENT) as s:
            session(config, tmp_path, RoutingBrain([d]), io).step("c10 group mein bhejo ke class 8 baje hai")
        assert io.asked == ["Send 'class 8 baje hai' to the WhatsApp group Class C10 (8 PM)? (yes/no)"]
        assert s.called is called


@pytest.fixture
def sched_env(config, tmp_path, monkeypatch):
    from assistant.tests.test_schedules import NOW, FakeScheduler
    sched = FakeScheduler()
    config.settings["scheduler"] = {"file": str(tmp_path / "schedules.yaml")}
    monkeypatch.setattr("assistant.skills._schedules.make_scheduler", lambda: sched)
    monkeypatch.setattr("assistant.skills._schedules.now", lambda: NOW)
    return config, tmp_path, sched


def test_group_message_can_be_scheduled(sched_env):
    config, tmp_path, sched = sched_env
    d = Decision(skill="schedule_task", params={"command": "c10 group mein good morning bhejo",
                                                "time": "09:00", "repeat": "daily"})
    inner = {"c10 group mein good morning bhejo":
             Decision(skill="send_whatsapp_group", params={"group": "c10", "message": "good morning"})}
    io = FakeIO(["haan"])
    session(config, tmp_path, RoutingBrain([d], inner), io).step("x")
    assert io.asked == ["Every day at 9:00 AM: send 'good morning' to the WhatsApp group Class C10 (8 PM). "
                        "Schedule it? (yes/no)"]
    tasks = load_tasks(tmp_path / "schedules.yaml")
    assert tasks[0].skill == "send_whatsapp_group" and tasks[0].params == {"group": "c10", "message": "good morning"}
