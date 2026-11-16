"""Shared WhatsApp Desktop helpers (the leading underscore keeps this out of skill discovery)."""
from __future__ import annotations

import os
from urllib.parse import quote


def chat_url(e164: str, message: str | None = None) -> str:
    """whatsapp://send?phone=923001234567[&text=<encoded>]. Spaces become %20, not '+',
    because WhatsApp can show a '+' literally."""
    url = f"whatsapp://send?phone={e164.lstrip('+')}"
    if message:
        url += "&text=" + quote(message, safe="")
    return url


def launch(url: str) -> None:
    os.startfile(url)  # opens WhatsApp Desktop; it never presses Send
