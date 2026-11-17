"""Phase 3.1: fuzzy suggestions, corrections, wake-phrase stripping, follow-up yes."""
import numpy as np
import pytest

from assistant.core.contacts import resolve_contact
from assistant.core.corrections import apply_corrections, load_corrections
from assistant.core.matching import similarity, suggest
from assistant.interfaces.stt import Transcriber, strip_wake_phrase
from assistant.skills.open_app import OpenApp


# --- fuzzy suggestions ---------------------------------------------------------------------
def test_similarity_uses_word_windows():
    assert similarity("Saad Atak Dad", "Saad Attock") >= 0.8
    assert similarity("chrome", "calculator") < 0.72


def test_close_contact_is_suggested_not_used(config):
    config.contacts = [c for c in config.contacts if c.name != "Ali Raza"]
    contact, question = resolve_contact(config.contacts, "Ali Kaan")
    assert contact is None and question == "Did you mean Ali Khan?"


def test_far_contact_still_says_not_found(config):
    contact, question = resolve_contact(config.contacts, "Bilal")
    assert contact is None and "contacts.yaml" in question


def test_app_typo_is_suggested_via_check(config):
    ask = OpenApp(config).check(app="crome")
    assert ask.text == "Did you mean chrome?" and ask.on_yes == {"app": "chrome"}
    assert OpenApp(config).check(app="chrome") is None
    assert "apps.yaml" in OpenApp(config).check(app="photoshop")


def test_suggest_orders_best_first():
    names = [("chrome", ["google chrome"]), ("calculator", ["calc"])]
    assert suggest("calculater", names) == ["calculator"]


# --- corrections ---------------------------------------------------------------------------
def test_corrections_whole_words_case_insensitive():
    fixes = {"gronkolo": "chrome kholo", "chilao": "chalao", "saad atak": "saad attock"}
    assert apply_corrections("Gronkolo.", fixes) == "chrome kholo."
    assert apply_corrections("Youtube chilao", fixes) == "Youtube chalao"
    assert apply_corrections("Saad Atak ko message", fixes) == "saad attock ko message"
    assert apply_corrections("chilaonga", fixes) == "chilaonga"            # not inside other words


def test_load_corrections(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("corrections:\n  gronkolo: chrome kholo\n  '633': six three three\n", encoding="utf-8")
    assert load_corrections(path) == {"gronkolo": "chrome kholo", "633": "six three three"}
    assert load_corrections(tmp_path / "missing.yaml") == {}


# --- wake phrase ---------------------------------------------------------------------------
@pytest.mark.parametrize("heard, expected", [
    ("Hey VigenX, how are you?", "how are you?"),
    ("Hey VisionX, chrome kholo", "chrome kholo"),
    ("Hey vijanx, Chrome kholo,", "Chrome kholo,"),
    ("Hey vision x youtube chalao", "youtube chalao"),
    ("VisionX time kya hua hai", "time kya hua hai"),
    ("Hi Saad, how are you", "Hi Saad, how are you"),        # not the wake phrase
    ("Hey VisionX", "Hey VisionX"),                           # nothing left: unchanged
    ("chrome kholo", "chrome kholo"),
])
def test_strip_wake_phrase(heard, expected):
    assert strip_wake_phrase(heard, "VisionX") == expected


class OneSTT:
    name, label = "groq", "Groq"

    def __init__(self, text):
        self.text = text

    def transcribe(self, audio, language, prompt):
        return self.text

    def warm_up(self):
        pass


def test_transcriber_strips_wake_phrase_then_corrects():
    t = Transcriber(OneSTT("Hey VigenX, Gronkolo."), None, assistant_name="VisionX",
                    corrections={"gronkolo": "chrome kholo"})
    assert t.transcribe(np.zeros(10, np.float32)).text == "chrome kholo."
