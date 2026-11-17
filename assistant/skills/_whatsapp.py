"""Shared WhatsApp Desktop helpers (the leading underscore keeps this out of skill discovery).

Auto-send uses Windows UI Automation (the accessibility API) to read WhatsApp's message box:
it only presses Enter when the box contains exactly the message VisionX typed, and it only
reports "sent" once the box has become empty. Learned on 2026-11-17: WhatsApp's deep link
APPENDS to an existing unsent draft, and a foreground-window check alone is not proof.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Protocol
from urllib.parse import quote

WHATSAPP_PROCESSES = frozenset({"whatsapp.root.exe", "whatsapp.exe"})
COMPOSE_PREFIX = "type a message"          # accessible name: "Type a message to <chat name>"

SENT, NOT_FRONT, NO_TEXT, DRAFT_CONFLICT, NOT_CLEARED = (
    "sent", "not_front", "no_text", "draft_conflict", "not_cleared")


def chat_url(e164: str, message: str | None = None) -> str:
    """whatsapp://send?phone=923001234567[&text=<encoded>]. Spaces become %20, not '+',
    because WhatsApp can show a '+' literally."""
    url = f"whatsapp://send?phone={e164.lstrip('+')}"
    if message:
        url += "&text=" + quote(message, safe="")
    return url


def launch(url: str) -> None:
    os.startfile(url)  # opens WhatsApp Desktop with the chat (and text) ready


def same_text(a: str, b: str) -> bool:
    squash = lambda s: re.sub(r"\s+", " ", s or "").strip()
    return squash(a) == squash(b)


# --- window / message box access (real implementations; tests inject fakes) ------------------
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


class ComposeBox(Protocol):
    def value(self) -> str: ...
    def focus(self) -> None: ...
    def click_send(self) -> bool: ...   # True if WhatsApp's Send button was found and clicked


class _UIABox:
    """WhatsApp's message box and Send button, through UI Automation. Clicking Send this way
    works even when WhatsApp isn't the window in front (Windows may refuse to bring it there)."""

    def __init__(self, uia: Any, window: Any, element: Any, ifaces: dict[str, Any]) -> None:
        self._uia, self._window, self._el, self._if = uia, window, element, ifaces

    def value(self) -> str:
        try:
            return self._el.GetCurrentPattern(10002).QueryInterface(self._if["value"]).CurrentValue or ""
        except Exception:
            return ""

    def focus(self) -> None:
        try:
            self._el.SetFocus()
        except Exception:
            pass

    def click_send(self) -> bool:
        try:
            cond = self._uia.CreateAndCondition(self._uia.CreatePropertyCondition(30003, 50000),  # Button
                                                self._uia.CreatePropertyCondition(30005, "Send"))   # Name
            button = self._window.FindFirst(4, cond)
            if not button:
                return False
            button.GetCurrentPattern(10000).QueryInterface(self._if["invoke"]).Invoke()
            return True
        except Exception:
            return False


def find_compose_box() -> ComposeBox | None:
    """WhatsApp's message box ("Type a message to ..."), via UI Automation; None if not found."""
    try:
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import (CUIAutomation, IUIAutomation,
                                                     IUIAutomationInvokePattern,
                                                     IUIAutomationValuePattern)
        uia = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
        window = uia.GetRootElement().FindFirst(2, uia.CreatePropertyCondition(30005, "WhatsApp"))
        if not window:
            return None
        edits = window.FindAll(4, uia.CreatePropertyCondition(30003, 50004))  # descendants, Edit
        for i in range(edits.Length):
            el = edits.GetElement(i)
            if (el.CurrentName or "").lower().startswith(COMPOSE_PREFIX):
                return _UIABox(uia, window, el, {"value": IUIAutomationValuePattern,
                                                 "invoke": IUIAutomationInvokePattern})
    except Exception:
        return None
    return None


def press_enter() -> None:
    from pynput.keyboard import Controller, Key
    kb = Controller()
    kb.press(Key.enter)
    kb.release(Key.enter)


# --- the send procedure ------------------------------------------------------------------------
def send_verified(message: str, timeout: float = 10.0, clear_timeout: float = 4.0,
                  foreground: Callable[[], str] = foreground_process,
                  find_box: Callable[[], ComposeBox | None] = find_compose_box,
                  press: Callable[[], None] = press_enter,
                  sleep: Callable[[float], None] = time.sleep,
                  clock: Callable[[], float] = time.monotonic) -> str:
    """Send only when WhatsApp's message box holds exactly `message`: click its Send button
    (works even if WhatsApp isn't in front); if the button can't be found, fall back to Enter,
    but only with WhatsApp in front. Return SENT only once the box has emptied."""
    deadline = clock() + timeout
    box, text = None, ""
    while clock() < deadline:
        box = find_box()
        text = box.value() if box else ""
        if box and message.strip() and message.strip() in text:
            break
        sleep(0.25)
    else:
        return NO_TEXT
    if not same_text(text, message):
        return DRAFT_CONFLICT                      # an old draft is in the box too: never send that

    if not box.click_send():
        box.focus()
        sleep(0.3)
        if foreground() not in WHATSAPP_PROCESSES:
            return NOT_FRONT
        press()

    clear_deadline = clock() + clear_timeout
    while clock() < clear_deadline:
        if not box.value().strip():
            return SENT
        sleep(0.25)
    return NOT_CLEARED
