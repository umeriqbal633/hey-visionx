import pytest

from assistant.core.confirm import confirm, is_yes


@pytest.mark.parametrize("answer", ["yes", "y", "haan", "han", "ji", "haan ji",
                                    "YES", " Haan Ji ", "yes.", "ji!"])
def test_accepts_explicit_yes(answer):
    assert is_yes(answer)


@pytest.mark.parametrize("answer", ["no", "n", "nahi", "", None, "ok", "sure",
                                    "yes please", "haan nahi", "yeah", "maybe"])
def test_everything_else_cancels(answer):
    assert not is_yes(answer)


def test_confirm_reads_back_prompt():
    asked = []
    assert confirm("Send it?", lambda q: asked.append(q) or "haan")
    assert asked == ["Send it? (yes/no)"]


def test_confirm_cancels_on_eof():
    def ask(_):
        raise EOFError
    assert confirm("Send it?", ask) is False
