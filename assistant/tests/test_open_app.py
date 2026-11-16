from unittest.mock import patch

from assistant.skills.open_app import OpenApp


def test_opens_by_name(config):
    with patch("assistant.skills.open_app._launch") as launch:
        result = OpenApp(config).run(app="chrome")
    launch.assert_called_once_with(r"C:\chrome.exe")
    assert result.ok and result.reply == "Opening chrome."


def test_opens_by_alias_case_insensitive(config):
    with patch("assistant.skills.open_app._launch") as launch:
        result = OpenApp(config).run(app="  Google Chrome ")
    launch.assert_called_once_with(r"C:\chrome.exe")
    assert result.ok


def test_opens_uri_target(config):
    with patch("assistant.skills.open_app._launch") as launch:
        OpenApp(config).run(app="calc")
    launch.assert_called_once_with("calculator:")


def test_unknown_app_is_not_launched_and_asks(config):
    with patch("assistant.skills.open_app._launch") as launch:
        result = OpenApp(config).run(app="photoshop")
    launch.assert_not_called()
    assert not result.ok and "apps.yaml" in result.reply


def test_launch_failure_is_friendly(config):
    with patch("assistant.skills.open_app._launch", side_effect=OSError("no handler")):
        result = OpenApp(config).run(app="whatsapp")
    assert not result.ok and "couldn't open whatsapp" in result.reply


def test_description_lists_known_apps(config):
    assert "chrome" in OpenApp(config).description
