"""Push-to-talk: hold the hotkey (e.g. ctrl+alt+space) to record, release to stop.

The key state machine (`key_down` / `key_up` with plain names) is separate from pynput so it
can be tested. While the hotkey's modifiers are held, its main key is swallowed so it doesn't
type into the app in front (e.g. a stray space).
"""
from __future__ import annotations

import threading
from typing import Any

MODIFIER_NAMES = {
    "ctrl_l": "ctrl", "ctrl_r": "ctrl", "ctrl": "ctrl",
    "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt", "alt": "alt",
    "shift_l": "shift", "shift_r": "shift", "shift": "shift",
    "cmd": "win", "cmd_l": "win", "cmd_r": "win",
}
VK_NAMES = {0x20: "space", **{0x70 + i: f"f{i + 1}" for i in range(12)},
            **{c: chr(c).lower() for c in range(0x41, 0x5B)}, **{c: chr(c) for c in range(0x30, 0x3A)}}
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105


def parse_hotkey(text: str) -> frozenset[str]:
    keys = frozenset(k.strip().lower().replace("control", "ctrl") for k in text.split("+") if k.strip())
    if len(keys) < 2:
        raise ValueError(f"hotkey needs at least two keys: {text!r}")
    return keys


class PushToTalk:
    def __init__(self, hotkey: str = "ctrl+alt+space") -> None:
        self.keys = parse_hotkey(hotkey)
        self.modifiers = frozenset(k for k in self.keys if k in MODIFIER_NAMES.values())
        self.main_keys = self.keys - self.modifiers
        self.held: set[str] = set()
        self.active = False
        self._pressed = threading.Event()
        self._released = threading.Event()
        self._listener: Any = None

    # --- state machine (tested directly) -------------------------------------------------
    def key_down(self, name: str) -> None:
        self.held.add(name)
        if not self.active and self.keys <= self.held:
            self.active = True
            self._released.clear()
            self._pressed.set()

    def key_up(self, name: str) -> None:
        self.held.discard(name)
        if self.active and name in self.keys:
            self.active = False
            self._pressed.clear()
            self._released.set()

    def wait_press(self, timeout: float | None = None) -> bool:
        return self._pressed.wait(timeout)

    def wait_release(self, timeout: float | None = None) -> bool:
        return self._released.wait(timeout)

    # --- pynput wiring --------------------------------------------------------------------
    @staticmethod
    def name_of(key: Any) -> str | None:
        name = getattr(key, "name", None)            # pynput Key enum (ctrl_l, alt_gr, space, ...)
        if name:
            return MODIFIER_NAMES.get(name, name)
        vk = getattr(key, "vk", None)                # KeyCode: letters/digits via virtual key code
        if vk is not None:
            return VK_NAMES.get(vk)
        char = getattr(key, "char", None)
        return char.lower() if char else None

    def _on_press(self, key: Any) -> None:
        name = self.name_of(key)
        if name:
            self.key_down(name)

    def _on_release(self, key: Any) -> None:
        name = self.name_of(key)
        if name:
            self.key_up(name)

    def _win32_filter(self, msg: int, data: Any) -> bool:
        """Swallow the main key while the modifiers are held; update state ourselves."""
        name = VK_NAMES.get(getattr(data, "vkCode", -1))
        if name in self.main_keys and self.modifiers <= self.held:
            if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                self.key_down(name)
            elif msg in (WM_KEYUP, WM_SYSKEYUP):
                self.key_up(name)
            self._listener.suppress_event()
        return True

    def start(self) -> None:
        from pynput import keyboard
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release,
                                           win32_event_filter=self._win32_filter)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
