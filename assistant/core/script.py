"""Writing-system checks. Speech-to-text may return Urdu (Arabic script), Latin (English /
Roman Urdu) or, wrongly, Devanagari for Roman Urdu speech. Devanagari must never get through."""
from __future__ import annotations

import re

DEVANAGARI = re.compile(r"[ऀ-ॿ꣠-ꣿ]")
ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
NON_LATIN_RUN = re.compile(
    r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿ऀ-ॿ꣠-ꣿ]"
    r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿ऀ-ॿ꣠-ꣿ\s،؟۔.,!?]*"
)


def has_devanagari(text: str) -> bool:
    return bool(DEVANAGARI.search(text or ""))


def has_arabic(text: str) -> bool:
    return bool(ARABIC.search(text or ""))


def script_of(text: str) -> str:
    """'devanagari', 'urdu', 'latin', or 'mixed' (for logs and the script test tool)."""
    dev, ara = has_devanagari(text), has_arabic(text)
    latin = bool(re.search(r"[A-Za-z]", text or ""))
    if dev:
        return "devanagari"
    if ara and latin:
        return "mixed"
    return "urdu" if ara else "latin"


def speakable(text: str) -> str:
    """A version of a reply that an English voice can read: drops '(+92 ...)' phone numbers and
    replaces quoted Urdu/Devanagari text with 'the message on screen'. The screen always shows
    the original text."""
    text = re.sub(r"\s*\(\+?[\d\s]{7,}\)", "", text)
    text = re.sub(r"'[^']*'", lambda m: "the message on screen" if NON_LATIN_RUN.search(m.group()) else m.group(), text)
    return NON_LATIN_RUN.sub("the text on screen ", text).replace("  ", " ").strip()
