from unittest.mock import patch

from assistant.interfaces.text_io import TextIO, clean


def test_clean_strips_bom_and_whitespace():
    assert clean("﻿chrome kholo \n") == "chrome kholo"


def test_listen_returns_clean_text():
    with patch("builtins.input", return_value="﻿  time kya hua hai "):
        assert TextIO().listen() == "time kya hua hai"


def test_listen_returns_none_on_eof():
    with patch("builtins.input", side_effect=EOFError):
        assert TextIO().listen() is None


def test_ask_cleans_answer():
    with patch("builtins.input", return_value="﻿haan"), patch("builtins.print"):
        assert TextIO().ask("Send?") == "haan"
