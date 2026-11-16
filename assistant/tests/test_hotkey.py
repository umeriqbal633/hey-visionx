from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from assistant.interfaces.hotkey import WM_KEYDOWN, WM_KEYUP, PushToTalk, parse_hotkey


def test_parse_hotkey():
    assert parse_hotkey("Ctrl+Alt+Space") == {"ctrl", "alt", "space"}
    with pytest.raises(ValueError):
        parse_hotkey("space")


def test_activates_only_when_all_keys_held():
    p = PushToTalk("ctrl+alt+space")
    p.key_down("ctrl"); p.key_down("space")
    assert not p.active
    p.key_down("alt")
    assert p.active and p.wait_press(0)


def test_releasing_any_hotkey_key_stops():
    p = PushToTalk("ctrl+alt+space")
    for k in ("ctrl", "alt", "space"):
        p.key_down(k)
    p.key_up("ctrl")
    assert not p.active and p.wait_release(0) and not p.wait_press(0)


def test_key_repeat_and_other_keys_are_harmless():
    p = PushToTalk("ctrl+alt+space")
    for k in ("ctrl", "alt", "space", "space", "space"):
        p.key_down(k)
    p.key_up("x")
    assert p.active


def test_key_names_from_pynput_objects():
    assert PushToTalk.name_of(SimpleNamespace(name="ctrl_l")) == "ctrl"
    assert PushToTalk.name_of(SimpleNamespace(name="alt_gr")) == "alt"
    assert PushToTalk.name_of(SimpleNamespace(name="space")) == "space"
    assert PushToTalk.name_of(SimpleNamespace(name=None, vk=0x41, char=None)) == "a"


def test_space_is_swallowed_only_while_modifiers_held():
    p = PushToTalk("ctrl+alt+space")
    p._listener = MagicMock()
    space = SimpleNamespace(vkCode=0x20)
    p._win32_filter(WM_KEYDOWN, space)              # no modifiers: passes through
    p._listener.suppress_event.assert_not_called()
    p.key_down("ctrl"); p.key_down("alt")
    p._win32_filter(WM_KEYDOWN, space)
    assert p.active and p._listener.suppress_event.called
    p._win32_filter(WM_KEYUP, space)
    assert not p.active
