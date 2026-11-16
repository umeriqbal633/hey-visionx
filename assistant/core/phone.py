"""Phone number normalization to E.164 (+923001234567), Pakistani formats first."""
from __future__ import annotations

import re


class PhoneError(ValueError):
    pass


def normalize_phone(raw: object) -> str:
    """'0300 1234567', '03001234567', '+92 300 1234567', '0092...', '92...' -> '+923001234567'.
    Other countries are accepted in +<country code> or 00<country code> form."""
    text = str(raw or "").strip()
    compact = re.sub(r"[\s\-().]", "", text)
    if not compact:
        raise PhoneError("empty number")

    if compact.startswith("+"):
        body = compact[1:]
    elif compact.startswith("00"):
        body = compact[2:]
    elif compact.startswith("0") and len(compact) == 11:      # 0300 1234567 (PK local)
        body = "92" + compact[1:]
    elif compact.startswith("92") and len(compact) == 12:     # 923001234567
        body = compact
    elif compact.startswith("3") and len(compact) == 10:      # 300 1234567
        body = "92" + compact
    else:
        raise PhoneError(f"unrecognised number: {text}")

    if not body.isdigit():
        raise PhoneError(f"number has invalid characters: {text}")
    if body.startswith("92"):
        if len(body) != 12:
            raise PhoneError(f"Pakistani numbers need 10 digits after +92: {text}")
    elif not 8 <= len(body) <= 15:
        raise PhoneError(f"wrong length: {text}")
    return "+" + body


def display_phone(e164: str) -> str:
    """'+923001234567' -> '+92 300 1234567' (other countries unchanged)."""
    if e164.startswith("+92") and len(e164) == 13:
        return f"+92 {e164[3:6]} {e164[6:]}"
    return e164
