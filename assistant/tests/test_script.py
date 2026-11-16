import pytest

from assistant.core.script import has_arabic, has_devanagari, script_of, speakable


def test_detects_devanagari():
    assert has_devanagari("मैं लेट हूँ")
    assert not has_devanagari("main late hoon")
    assert not has_devanagari("میں لیٹ ہوں")


def test_detects_urdu_script():
    assert has_arabic("میں لیٹ ہوں") and not has_arabic("main late hoon")


@pytest.mark.parametrize("text, script", [
    ("main late hoon", "latin"), ("میں لیٹ ہوں", "urdu"), ("मैं लेट हूँ", "devanagari"),
    ("Ali کو message", "mixed"), ("Ali को message", "devanagari"),
])
def test_script_of(text, script):
    assert script_of(text) == script


def test_speakable_keeps_latin_and_drops_phone():
    assert speakable("Send 'main late hoon' to Ali Khan (+92 300 1234567)? (yes/no)") == \
        "Send 'main late hoon' to Ali Khan? (yes/no)"


def test_speakable_replaces_urdu_message():
    spoken = speakable("Send 'میں لیٹ ہوں' to Ali Khan (+92 300 1234567)? (yes/no)")
    assert spoken == "Send the message on screen to Ali Khan? (yes/no)"
    assert not has_arabic(spoken)


def test_speakable_never_speaks_devanagari():
    assert not has_devanagari(speakable("Opening मैं chrome"))
