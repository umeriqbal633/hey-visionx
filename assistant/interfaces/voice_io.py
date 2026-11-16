"""Phase 3 interface: push-to-talk speech in, spoken + printed replies out."""
from __future__ import annotations

from typing import Callable

from assistant.core.confirm import VOICE_YES_WORDS
from assistant.core.timing import Timings
from assistant.interfaces.audio import Recorder, beep
from assistant.interfaces.hotkey import PushToTalk
from assistant.interfaces.stt import Transcriber
from assistant.interfaces.tts import Speaker


class VoiceIO:
    extra_yes = VOICE_YES_WORDS          # how STT writes a spoken "ji" (e.g. "G")
    confirm_hint = "(say yes or ji)"

    def __init__(self, ptt: PushToTalk, recorder: Recorder, transcriber: Transcriber, speaker: Speaker,
                 assistant_name: str = "VisionX", hotkey_label: str = "ctrl+alt+space",
                 min_seconds: float = 0.3, beeps: bool = True,
                 printer: Callable[[str], None] = print, beeper: Callable[[str], None] = beep) -> None:
        self.ptt, self.recorder, self.transcriber, self.speaker = ptt, recorder, transcriber, speaker
        self.name = assistant_name
        self.hotkey_label = hotkey_label
        self.min_seconds = min_seconds
        self.beeps = beeps
        self.print = printer
        self.beep = beeper

    def _record(self) -> tuple[object, float]:
        self.ptt.wait_press()
        if self.beeps:
            self.beep("start")
        self.recorder.start()
        self.ptt.wait_release()
        audio = self.recorder.stop()
        if self.beeps:
            self.beep("stop")
        return audio, self.recorder.seconds(audio)

    def listen(self, timings: Timings | None = None) -> str | None:
        """Wait for one push-to-talk utterance and return its text (never Devanagari)."""
        while True:
            audio, seconds = self._record()
            if seconds < self.min_seconds:
                self.print(f"(ignored a {seconds:.1f}s recording; hold {self.hotkey_label} while you speak)")
                continue
            if timings is not None:
                timings.add("rec", seconds)
            if timings is not None:
                with timings.step("stt"):
                    result = self.transcriber.transcribe(audio)
            else:
                result = self.transcriber.transcribe(audio)
            for notice in result.notices:
                self.say(notice)
            if not result.text:
                if not result.notices:
                    self.say("Sorry, I didn't catch that.")
                continue
            self.print(f"You (voice): {result.text}")
            return result.text

    def say(self, text: str) -> None:
        self.print(f"{self.name}: {text}")
        self.speaker.say(text)

    def note(self, text: str) -> None:
        """Printed only, never spoken (timings, hints)."""
        self.print(text)

    def ask(self, question: str) -> str:
        self.say(question)
        return self.listen() or ""
