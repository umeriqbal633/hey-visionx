from unittest.mock import patch

import pytest

from assistant.skills.open_website import GOOGLE_SEARCH, OpenWebsite


def run(config, target):
    with patch("assistant.skills.open_website._open") as opener:
        result = OpenWebsite(config).run(target=target)
    return result, opener


@pytest.mark.parametrize("target", ["youtube", "YouTube", "you tube", "yt",
                                    "youtube.com", "https://www.youtube.com/"])
def test_allowlisted_site_opens_its_url(config, target):
    result, opener = run(config, target)
    opener.assert_called_once_with("https://www.youtube.com")
    assert result.ok and result.reply == "Opening youtube."


def test_unknown_site_becomes_google_search(config):
    result, opener = run(config, "biryani recipe")
    opener.assert_called_once_with(GOOGLE_SEARCH + "biryani+recipe")
    assert result.ok and "Searching Google" in result.reply


@pytest.mark.parametrize("target", ["https://evil.example.com/login",
                                    "javascript:alert(1)", "file:///C:/Windows"])
def test_arbitrary_urls_are_never_opened_directly(config, target):
    _, opener = run(config, target)
    (url,), _ = opener.call_args
    assert url.startswith(GOOGLE_SEARCH)
    assert ":" not in url[len(GOOGLE_SEARCH):]  # the text is fully URL-encoded


def test_urdu_text_is_encoded(config):
    _, opener = run(config, "موسم لاہور")
    (url,), _ = opener.call_args
    assert url.startswith(GOOGLE_SEARCH) and "%" in url


def test_empty_target_asks(config):
    result, opener = run(config, "  ")
    opener.assert_not_called()
    assert not result.ok
