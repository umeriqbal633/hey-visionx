import pytest

from assistant.core.phone import PhoneError, display_phone, normalize_phone


@pytest.mark.parametrize("raw", [
    "0300 1234567", "03001234567", "+92 300 1234567", "+923001234567",
    "923001234567", "0092 300 1234567", "300 1234567", "0300-1234567",
    " (0300) 123-4567 ", 3001234567,
])
def test_pakistani_formats_normalize(raw):
    assert normalize_phone(raw) == "+923001234567"


def test_other_country_in_plus_form():
    assert normalize_phone("+44 20 7946 0958") == "+442079460958"


@pytest.mark.parametrize("raw", ["", "12345", "0300 12345", "+92 300 12345678",
                                 "0300 123456a", "abc", "+", None])
def test_invalid_numbers_raise(raw):
    with pytest.raises(PhoneError):
        normalize_phone(raw)


def test_display_format():
    assert display_phone("+923001234567") == "+92 300 1234567"
    assert display_phone("+442079460958") == "+442079460958"
