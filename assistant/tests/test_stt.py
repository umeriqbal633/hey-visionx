import numpy as np

from assistant.core.script import has_devanagari
from assistant.interfaces.stt import Transcriber, get_transcriber
from assistant.interfaces.stt.base import STTError, STTProvider

AUDIO = np.zeros(16000, dtype=np.float32)


class FakeSTT(STTProvider):
    def __init__(self, name, label, outputs):
        self.name, self.label = name, label
        self.outputs = list(outputs)   # one per call: text or an exception
        self.calls = []

    def transcribe(self, audio, language, prompt):
        self.calls.append((language, prompt))
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def groq(*outputs):
    return FakeSTT("groq", "Groq", outputs)


def local(*outputs):
    return FakeSTT("local", "offline transcription", outputs)


def test_primary_used_with_language_and_prompt():
    p = groq("chrome kholo")
    t = Transcriber(p, local(), language="en", prompt="Roman Urdu").transcribe(AUDIO)
    assert t.text == "chrome kholo" and t.provider == "groq" and t.notices == []
    assert p.calls == [("en", "Roman Urdu")]


def test_rate_limit_falls_back_to_local_and_says_so():
    t = Transcriber(groq(STTError("Groq's speech recognition is rate limited right now.")),
                    local("chrome kholo")).transcribe(AUDIO)
    assert t.text == "chrome kholo" and t.provider == "local"
    assert t.notices == ["Groq is unavailable, so I used offline transcription."]


def test_both_fail_returns_empty_with_notice():
    t = Transcriber(groq(STTError("x")), local(STTError("y"))).transcribe(AUDIO)
    assert t.text == "" and len(t.notices) == 1


def test_devanagari_is_retried_in_urdu_script():
    p = groq("मैं लेट हूँ", "میں لیٹ ہوں")
    t = Transcriber(p, local(), language=None, prompt="hint", retry_language="ur").transcribe(AUDIO)
    assert t.text == "میں لیٹ ہوں"
    assert p.calls == [(None, "hint"), ("ur", None)]


def test_devanagari_never_gets_through():
    t = Transcriber(groq("मैं लेट हूँ", "फिर से हिंदी"), local()).transcribe(AUDIO)
    assert t.text == "" and not has_devanagari(t.text)
    assert any("wrong script" in n for n in t.notices)


def test_devanagari_blocked_even_without_retry_language():
    t = Transcriber(groq("मैं"), None, retry_language=None).transcribe(AUDIO)
    assert t.text == ""


def test_get_transcriber_without_groq_key_uses_local(config):
    config.secrets = {}
    config.settings["stt"] = {"provider": "groq", "fallback": "local", "language": "en"}
    transcriber, notices = get_transcriber(config)
    assert transcriber.primary.name == "local" and transcriber.fallback is None
    assert notices and "GROQ_API_KEY" in notices[0]
