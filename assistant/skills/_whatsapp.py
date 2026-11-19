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


def _plain(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def same_text(a: str, b: str) -> bool:
    """Equal apart from spacing and line breaks (WhatsApp may store new lines differently)."""
    return _plain(a) == _plain(b)


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

    def name(self) -> str:
        """Accessible name: 'Type a message to <person>' or 'Type a message to group <group>'."""
        try:
            return self._el.CurrentName or ""
        except Exception:
            return ""

    def click_into(self) -> bool:
        """A real mouse click in the box. Learned live (2026-11-19): after UIA SetFocus alone,
        typed keys never reach WhatsApp's message box; after a click they do. Clicks only if
        the spot is really this box (not another window covering WhatsApp)."""
        return _safe_click(self._uia, self._el)

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


def _uia() -> tuple[Any, Any, dict[str, Any]] | None:
    """(automation, WhatsApp window element, pattern interfaces), or None."""
    try:
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import (CUIAutomation, IUIAutomation,
                                                     IUIAutomationInvokePattern,
                                                     IUIAutomationLegacyIAccessiblePattern,
                                                     IUIAutomationValuePattern)
        uia = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
        window = uia.GetRootElement().FindFirst(2, uia.CreatePropertyCondition(30005, "WhatsApp"))
        if not window:
            return None
        return uia, window, {"value": IUIAutomationValuePattern, "invoke": IUIAutomationInvokePattern,
                             "legacy": IUIAutomationLegacyIAccessiblePattern}
    except Exception:
        return None


def _edit_named(uia: Any, window: Any, prefix: str) -> Any:
    edits = window.FindAll(4, uia.CreatePropertyCondition(30003, 50004))  # descendants, Edit
    for i in range(edits.Length):
        el = edits.GetElement(i)
        if (el.CurrentName or "").lower().startswith(prefix):
            return el
    return None


def find_compose_box() -> ComposeBox | None:
    """WhatsApp's message box ("Type a message to ..."), via UI Automation; None if not found."""
    found = _uia()
    if not found:
        return None
    uia, window, ifaces = found
    try:
        el = _edit_named(uia, window, COMPOSE_PREFIX)
        return _UIABox(uia, window, el, ifaces) if el else None
    except Exception:
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
        if box and message.strip() and _plain(message) in _plain(text):
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


# --- groups: no phone number, so open the chat through WhatsApp's search ----------------------
# A group has no whatsapp:// link. VisionX types the group's exact name into "Search or start a
# new chat", opens the matching result, and only continues once the message box is named
# "Type a message to group <exact name>". Nothing is typed into any other chat.
SEARCH_PREFIX = "search or start a new chat"
NOT_FOUND, WRONG_CHAT, TYPED = "not_found", "wrong_chat", "typed"
_UNREAD = re.compile(r"^\d+ unread messages? ", re.IGNORECASE)


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip().lower()


def is_group_chat(box_name: str, group: str) -> bool:
    """True only if the open chat is exactly this group."""
    return _squash(box_name) == _squash(f"type a message to group {group}")


def result_matches(title: str, group: str) -> bool:
    """A search result like '2 unread messages Class C10 (8 PM) 8:21 pm' is this group.
    'Class C1' does not match 'Class C10 (8 PM)': the name must be followed by a space or end."""
    t, g = _UNREAD.sub("", _squash(title)), _squash(group)
    return t == g or t.startswith(g + " ")


def matching_chats(titles: list[str], group: str) -> int:
    """How many different chats in the search results carry exactly this name. Each chat shows
    as several rows ('NAME 2:05 am You: …' and 'NAME 2:05 am'); its last-activity label
    ('2:05 am', 'Yesterday', '26/10/2026') tells chats apart. Seen live: two groups both named
    'VXC C17 (7PM)', one from October."""
    g, labels = _squash(group), set()
    for title in titles:
        if not result_matches(title, group):
            continue
        rest = _UNREAD.sub("", _squash(title))[len(g):].split()
        label = rest[:2] if len(rest) > 1 and rest[1] in ("am", "pm") else rest[:1]
        labels.add(" ".join(label))
    return len(labels)


AMBIGUOUS = "ambiguous"


class ChatWindow(Protocol):
    def compose(self) -> ComposeBox | None: ...
    def search(self, text: str) -> bool: ...
    def results(self) -> list[str]: ...
    def open_result(self, title: str, click: bool = False) -> bool: ...
    def type_text(self, text: str) -> None: ...
    def clear_search(self) -> None: ...
    def bring_to_front(self) -> None: ...


class _UIAWindow:
    """The real WhatsApp window, through UI Automation (keyboard and mouse via pynput)."""

    def __init__(self, uia: Any, window: Any, ifaces: dict[str, Any]) -> None:
        self._uia, self._window, self._if = uia, window, ifaces

    def compose(self) -> ComposeBox | None:
        try:
            el = _edit_named(self._uia, self._window, COMPOSE_PREFIX)
            return _UIABox(self._uia, self._window, el, self._if) if el else None
        except Exception:
            return None

    def bring_to_front(self) -> None:
        """Restore WhatsApp and make it the foreground window. Opening 'whatsapp:' alone doesn't
        (Windows blocks background apps from taking focus; seen live 2026-11-20). Tapping Alt first
        is the standard way to be allowed to call SetForegroundWindow."""
        import ctypes
        try:
            user32 = ctypes.windll.user32
            hwnd = self._window.CurrentNativeWindowHandle
            if not hwnd:
                return
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)                  # SW_RESTORE
            user32.keybd_event(0x12, 0, 0, 0)               # Alt down
            user32.keybd_event(0x12, 0, 2, 0)               # Alt up
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _search_box(self) -> Any:
        """The search box. While it holds text its accessible name is BLANK (seen live
        2026-11-20), so fall back to the one unnamed edit box (the message box always has a name)."""
        box = _edit_named(self._uia, self._window, SEARCH_PREFIX)
        if box:
            return box
        edits = self._window.FindAll(4, self._uia.CreatePropertyCondition(30003, 50004))
        for i in range(edits.Length):
            el = edits.GetElement(i)
            if not (el.CurrentName or "").strip():
                return el
        return None

    def _set_search(self, text: str) -> bool:
        """Learned live (2026-11-19): typed keys don't reach the search box, and ValuePattern
        sets the text without filtering; the LegacyIAccessible SetValue does filter."""
        try:
            box = self._search_box()
            if not box:
                return False
            box.SetFocus()
            box.GetCurrentPattern(10018).QueryInterface(self._if["legacy"]).SetValue(text)
            return True
        except Exception:
            return False

    def search(self, text: str) -> bool:
        return self._set_search(text)

    def clear_search(self) -> None:
        self._set_search("")

    def _result_items(self) -> list[Any]:
        try:
            grid = self._window.FindFirst(4, self._uia.CreatePropertyCondition(30005, "Search results."))
            if not grid:
                return []
            items = grid.FindAll(4, self._uia.CreatePropertyCondition(30003, 50029))  # DataItem
            return [items.GetElement(i) for i in range(items.Length)]
        except Exception:
            return []

    def results(self) -> list[str]:
        names = []
        for el in self._result_items():
            try:
                names.append(el.CurrentName or "")
            except Exception:
                pass
        return names

    def open_result(self, title: str, click: bool = False) -> bool:
        for el in self._result_items():
            try:
                if (el.CurrentName or "") != title:
                    continue
                if not click:
                    el.GetCurrentPattern(10018).QueryInterface(self._if["legacy"]).DoDefaultAction()
                    return True
                return _safe_click(self._uia, el)
            except Exception:
                continue
        return False

    def type_text(self, text: str) -> None:
        """Type into the focused message box. A new line is Shift+Enter (Enter would send);
        '@all' is turned into WhatsApp's real 'mention all members' by pressing its button."""
        from pynput.keyboard import Controller, Key
        kb = Controller()
        for n, line in enumerate(text.split("\n")):
            if n:
                with kb.pressed(Key.shift):
                    kb.tap(Key.enter)
            for part in re.split(r"(@all\b)", line, flags=re.IGNORECASE):
                if not part:
                    continue
                kb.type(part)
                if part.lower() == "@all":
                    self._pick_mention_all()

    def _pick_mention_all(self, seconds: float = 2.0) -> bool:
        """Press WhatsApp's 'all  Mention all members in this chat' suggestion."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                buttons = self._window.FindAll(4, self._uia.CreatePropertyCondition(30003, 50000))
                for i in range(buttons.Length):
                    b = buttons.GetElement(i)
                    if (b.CurrentName or "").lower().startswith("all mention all members"):
                        b.GetCurrentPattern(10000).QueryInterface(self._if["invoke"]).Invoke()
                        time.sleep(0.3)
                        return True
            except Exception:
                pass
            time.sleep(0.2)
        return False


def _safe_click(uia: Any, el: Any) -> bool:
    """Left-click the middle of `el`, but only if the element at that screen point is `el`
    itself (or inside it): never click a window that is covering WhatsApp."""
    import ctypes
    from ctypes import wintypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # match UIA's pixels
    except Exception:
        pass
    try:
        r = el.CurrentBoundingRectangle
        x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
        if r.right <= r.left or r.bottom <= r.top:
            return False
        at = uia.ElementFromPoint(wintypes.POINT(x, y))
        # WhatsApp's tree holds many copies of each element, so identity checks fail at random
        # (seen live 2026-11-20): accept the same element, or one with the same type and name.
        kind, name = el.CurrentControlType, el.CurrentName or ""
        walker, node, ok = uia.ControlViewWalker, at, False
        for _ in range(8):                                   # the hit may be a child of el
            if not node:
                break
            if uia.CompareElements(node, el) or (
                    name and node.CurrentControlType == kind and (node.CurrentName or "") == name):
                ok = True
                break
            node = walker.GetParentElement(node)
        if not ok:
            return False
        from pynput.mouse import Button, Controller
        mouse = Controller()
        mouse.position = (x, y)
        mouse.click(Button.left)
        return True
    except Exception:
        return False


def find_window() -> ChatWindow | None:
    found = _uia()
    return _UIAWindow(*found) if found else None


def send_to_group(group: str, message: str, send: bool = True, timeout: float = 10.0,
                  pick_newest: bool = False,
                  clear_timeout: float = 4.0,
                  open_app: Callable[[], None] = lambda: launch("whatsapp:"),
                  window: Callable[[], ChatWindow | None] = find_window,
                  foreground: Callable[[], str] = foreground_process,
                  sleep: Callable[[float], None] = time.sleep,
                  clock: Callable[[], float] = time.monotonic) -> str:
    """Open the group's chat through search, type `message`, and (if `send`) send it verified.
    Returns SENT, TYPED (send=False), or why it stopped: NOT_FRONT, NOT_FOUND, WRONG_CHAT,
    DRAFT_CONFLICT, NO_TEXT, NOT_CLEARED. Keys are only pressed while WhatsApp is in front."""
    # Keep the user's lines (typed as Shift+Enter by type_text); tidy spaces inside each line.
    text = "\n".join(" ".join(line.split()) for line in message.strip().splitlines())
    in_front = lambda: foreground() in WHATSAPP_PROCESSES

    def wait(condition: Callable[[], Any], seconds: float) -> Any:
        end = clock() + seconds
        while clock() < end:
            value = condition()
            if value:
                return value
            sleep(0.25)
        return None

    def target_box() -> ComposeBox | None:
        win = window()
        box = win.compose() if win else None
        return box if box and is_group_chat(box.name(), group) else None

    open_app()
    win = wait(window, timeout)
    if not win:
        return NOT_FRONT

    if not target_box():                                         # not already open: search for it
        if not win.search(group):
            return NOT_FOUND
        title = wait(lambda: next((t for t in win.results() if result_matches(t, group)), None), timeout)
        if not title:
            win.clear_search()
            return NOT_FOUND
        sleep(0.5)                                               # let the list finish filling
        if matching_chats(win.results(), group) > 1:             # two groups, same name
            if not pick_newest:
                win.clear_search()
                return AMBIGUOUS
            # WhatsApp lists the most recently active chat first: use that one.
            title = next(t for t in win.results() if result_matches(t, group))
        for click in (False, True):                              # accessibility action, then a click
            win.open_result(title, click=click)
            if wait(target_box, 2.0):
                break
        else:
            win.clear_search()
            return WRONG_CHAT

    box = target_box()
    if box is None:
        return WRONG_CHAT
    if box.value().strip():
        return DRAFT_CONFLICT                                    # someone's unsent text: leave it
    win.bring_to_front()
    wait(in_front, 2.0)
    if not box.click_into():                     # refuses if another window covers the box
        return NOT_FRONT
    if not wait(lambda: in_front() and target_box(), 2.0):        # keys only go to WhatsApp
        return NOT_FRONT
    win.type_text(text)
    if not send:
        return TYPED if wait(lambda: same_text(box.value(), text), timeout) else NO_TEXT
    return send_verified(text, timeout=timeout, clear_timeout=clear_timeout, foreground=foreground,
                         find_box=target_box, sleep=sleep, clock=clock)
