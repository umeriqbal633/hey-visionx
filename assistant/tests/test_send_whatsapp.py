from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from assistant.core.brain import Decision
from assistant.core.logger import ActionLogger
from assistant.core.registry import discover
from assistant.main import handle
from assistant.skills._whatsapp import chat_url
from assistant.skills.send_whatsapp import SendWhatsApp

LAUNCH = "assistant.skills._whatsapp.launch"


def test_is_a_confirm_skill(config):
    assert SendWhatsApp(config).risk == "confirm"


def test_read_back_wording(config):
    prompt = SendWhatsApp(config).confirm_prompt(contact="ali bhai", message="main late hoon")
    assert prompt == "Send 'main late hoon' to Ali Khan (+92 300 1234567)?"


def test_check_asks_for_duplicates_and_unknowns(config):
    skill = SendWhatsApp(config)
    assert skill.check(contact="Ali", message="hi") == "Which Ali do you mean: Ali Khan or Ali Raza?"
    assert "contacts.yaml" in skill.check(contact="Bilal", message="hi")
    assert skill.check(contact="Ali Khan", message="hi") is None


def test_run_opens_whatsapp_with_typed_message(config):
    with patch(LAUNCH) as launch:
        result = SendWhatsApp(config).run(contact="Ali Khan", message="main late hoon")
    launch.assert_called_once_with("whatsapp://send?phone=923001234567&text=main%20late%20hoon")
    assert result.ok and "press Enter" in result.reply


@pytest.mark.parametrize("message", [
    "main late hoon",                          # Roman Urdu
    "Kya haal hai? 10 min mein aa raha hoon & khana ready rakhna!",
    "میں لیٹ ہوں",                             # Urdu script
    "50% done, ok? #1 + more",
])
def test_message_is_encoded_and_round_trips_exactly(message):
    url = chat_url("+923001234567", message)
    assert " " not in url and "+" not in url.split("text=")[1]
    query = urlparse(url).query
    assert parse_qs(query)["text"] == [message]
    assert unquote(url.split("text=")[1]) == message


def test_open_chat_url_has_no_text():
    assert chat_url("+923001234567") == "whatsapp://send?phone=923001234567"


def test_launch_failure_is_friendly(config):
    with patch(LAUNCH, side_effect=OSError):
        result = SendWhatsApp(config).run(contact="Ali Khan", message="hi")
    assert not result.ok and "WhatsApp" in result.reply


class FakeBrain:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, _):
        return self.decision


class FakeIO:
    def __init__(self, answer):
        self.answer, self.said, self.asked = answer, [], []

    def say(self, t):
        self.said.append(t)

    def ask(self, q):
        self.asked.append(q)
        return self.answer


def run_flow(config, tmp_path, contact, answer="haan"):
    decision = Decision(skill="send_whatsapp", params={"contact": contact, "message": "main late hoon"})
    io = FakeIO(answer)
    with patch(LAUNCH) as launch:
        handle("x", FakeBrain(decision), discover(config), io, ActionLogger(tmp_path / "a.jsonl"))
    return io, launch


def test_full_flow_sends_only_after_yes(config, tmp_path):
    io, launch = run_flow(config, tmp_path, "ali bhai", "haan ji")
    assert io.asked == ["Send 'main late hoon' to Ali Khan (+92 300 1234567)? (yes/no)"]
    launch.assert_called_once()


def test_full_flow_no_means_nothing_opens(config, tmp_path):
    io, launch = run_flow(config, tmp_path, "ali bhai", "nahi")
    launch.assert_not_called()
    assert io.said[-1] == "Okay, cancelled."


def test_full_flow_duplicate_asks_before_any_read_back(config, tmp_path):
    io, launch = run_flow(config, tmp_path, "Ali")
    launch.assert_not_called()
    assert io.asked == []
    assert io.said == ["Which Ali do you mean: Ali Khan or Ali Raza?"]
