"""Shared WhatsApp Desktop helpers (the leading underscore keeps this out of skill discovery)."""
from __future__ import annotations

import os
import time
from typing import Callable
from urllib.parse import quote

WHATSAPP_PROCESSES = frozenset({"whatsapp.root.exe", "whatsapp.exe"})


def chat_url(e164: str, message: str | None = None) -> str:
    """whatsapp://send?phone=923001234567[&text=<encoded>]. Spaces become %20, not '+',
    because WhatsApp can show a '+' literally."""
    url = f"whatsapp://send?phone={e164.lstrip('+')}"
    if message:
        url += "&text=" + quote(message, safe="")
    return url


def launch(url: str) -> None:
    os.startfile(url)  # opens WhatsApp Desktop with the chat (and text) ready


def foreground_process() -> str:
    """Lower-case exe name of the window in front, e.g. 'whatsapp.root.exe' ('' if unknown)."""
    try:
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return ""
            return os.path.basename(buf.value).lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return ""


def press_enter() -> None:
    from pynput.keyboard import Controller, Key
    kb = Controller()
    kb.press(Key.enter)
    kb.release(Key.enter)


def send_when_ready(timeout: float = 10.0, settle: float = 2.0,
                    foreground: Callable[[], str] = foreground_process,
                    press: Callable[[], None] = press_enter,
                    sleep: Callable[[float], None] = time.sleep,
                    clock: Callable[[], float] = time.monotonic) -> bool:
    """Press Enter only if WhatsApp is the window in front, both before and after giving the
    chat time to load. Returns False (nothing pressed) if WhatsApp never came to the front."""
    deadline = clock() + timeout
    while foreground() not in WHATSAPP_PROCESSES:
        if clock() >= deadline:
            return False
        sleep(0.25)
    sleep(settle)                                  # let the chat open and the text appear
    if foreground() not in WHATSAPP_PROCESSES:     # user switched away meanwhile: don't type into it
        return False
    press()
    return True
