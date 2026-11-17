from unittest.mock import MagicMock

import numpy as np

from assistant.core.confirm import confirm
from assistant.core.timing import Timings
from assistant.interfaces.stt import Transcript
from assistant.interfaces.tts import Speaker
from assistant.interfaces.voice_io import VoiceIO


class FakePTT:
    def wait_press(self, timeout=None):
        return True

    def wait_release(self, timeout=None):
        return True


class FakeRecorder:
    def __init__(self, lengths):
        self.lengths = list(lengths)

    def start(self):
        pass

    def stop(self):
        return np.zeros(int(self.lengths.pop(0) * 16000), np.float32)

    def seconds(self, audio):
        return len(audio) / 16000


class FakeTranscriber:
    def __init__(self, *results):
        self.results = list(results)

    def transcribe(self, audio):
        r = self.results.pop(0)
        return r if isinstance(r, Transcript) else Transcript(text=r, provider="groq")


def make(lengths, *results):
    printed, beeps = [], []
    speaker = MagicMock()
    io = VoiceIO(FakePTT(), FakeRecorder(lengths), FakeTranscriber(*results), speaker,
                 printer=printed.append, beeper=beeps.append)
    return io, printed, speaker, beeps


def test_listen_returns_text_and_beeps():
    io, printed, _, beeps = make([1.2], "chrome kholo")
    t = Timings()
    assert io.listen(t) == "chrome kholo"
    assert beeps == ["start", "stop"]
    assert t.steps["rec"] == 1.2 and "stt" in t.steps
    assert "You (voice): chrome kholo" in printed


def test_short_recordings_are_ignored():
    io, printed, _, _ = make([0.1, 0.25, 1.0], "time kya hua hai")
    assert io.listen() == "time kya hua hai"
    assert sum("ignored" in p for p in printed) == 2


def test_fallback_notice_is_spoken():
    io, printed, speaker, _ = make([1.0], Transcript("chrome kholo", "local",
                                                      ["Groq is unavailable, so I used offline transcription."]))
    io.listen()
    speaker.say.assert_any_call("Groq is unavailable, so I used offline transcription.")


def test_empty_transcript_asks_again():
    io, printed, speaker, _ = make([1.0, 1.0], "", "youtube chalao")
    assert io.listen() == "youtube chalao"
    speaker.say.assert_any_call("Sorry, I didn't catch that.")


def test_voice_confirmation_with_existing_confirm():
    # Real transcripts from the voice test: "ji" came back as "G", "haan" as "Haan." or "Huh."
    # Unclear answers get one retry ("Please say yes or no."); the second answer decides.
    for answers, expected in [(["Haan."], True), (["Yes."], True), (["Ji"], True), (["ہاں"], True),
                              (["G."], True), (["Jee"], True), (["ہا."], True), (["No."], False),
                              (["Huh.", "Yes."], True), (["Gigi", "Ji"], True),
                              (["Huh.", "Huh."], False), (["Thank you.", "No."], False)]:
        io, _, _, _ = make([0.8] * len(answers), *answers)
        assert confirm("Send 'hi' to Ali?", io.ask, io.extra_yes, io.confirm_hint) is expected, answers


def test_voice_read_back_hint():
    io, printed, _, _ = make([0.8], "G")
    confirm("Send 'hi' to Ali?", io.ask, io.extra_yes, io.confirm_hint)
    assert "VisionX: Send 'hi' to Ali? (say yes or ji)" in printed


def test_typed_mode_stays_strict():
    assert not confirm("Send?", lambda q: "G")


def test_speaker_speaks_english_readable_version():
    engine = MagicMock()
    Speaker(engine=engine).say("Send 'میں لیٹ ہوں' to Ali Khan (+92 300 1234567)? (yes/no)")
    engine.say.assert_called_once_with("Send the message on screen to Ali Khan? (yes/no)")


def test_speaker_never_crashes():
    engine = MagicMock()
    engine.runAndWait.side_effect = RuntimeError("audio device gone")
    Speaker(engine=engine).say("hello")
