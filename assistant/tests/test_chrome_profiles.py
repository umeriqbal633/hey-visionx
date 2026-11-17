import json
from unittest.mock import patch

import pytest

from assistant.core.chrome_profiles import Profile, find_profiles, load_profiles, resolve_profile
from assistant.skills.open_chrome_profile import OpenChromeProfile
from assistant.skills.open_website import GOOGLE_SEARCH

# Fake profiles shaped like this PC's (names only; emails are made up).
PROFILES = [
    Profile("Default", "Muhammad", "muhammad.test@gmail.com"),
    Profile("Profile 2", "isb.nu.edu.pk", "student@isb.nu.edu.pk"),
    Profile("Profile 3", "Saad", "saad.test@gmail.com"),
    Profile("Profile 4", "visionxcoders.com", "team@visionxcoders.com"),
    Profile("Profile 5", "Umer", "xumar633@gmail.com"),
]


@pytest.fixture
def chrome_dir(tmp_path):
    cache = {p.directory: {"name": p.name, "user_name": p.email} for p in PROFILES}
    (tmp_path / "Local State").write_text(json.dumps({"profile": {"info_cache": cache}}), encoding="utf-8")
    return tmp_path


def test_load_profiles_from_local_state(chrome_dir):
    assert load_profiles(chrome_dir) == sorted(PROFILES, key=lambda p: p.directory)
    assert load_profiles(chrome_dir / "nope") == []


@pytest.mark.parametrize("said, directory", [
    ("Umer", "Profile 5"),
    ("Umer wala Chrome", "Profile 5"),
    ("xumar633", "Profile 5"),
    ("xumar633.gmail.com wale chrome browser", "Profile 5"),
    ("xumar633@gmail.com", "Profile 5"),
    ("visionxcoders", "Profile 4"),
    ("isb.nu.edu.pk wala", "Profile 2"),
])
def test_profile_matching(said, directory):
    profile, question = resolve_profile(PROFILES, said)
    assert question is None and profile.directory == directory


def test_misheard_email_is_suggested_not_opened():
    profile, question = resolve_profile(PROFILES, "I umar633x")
    assert profile is None and question == "Did you mean the Umer (…633) Chrome profile?"


def test_matching_digits_point_to_the_account():
    profiles = [Profile("Default", "Muhammad", "xumer633@gmail.com"),
                Profile("Profile 5", "Umer", "amxyz634@gmail.com")]
    profile, question = resolve_profile(profiles, "umar633x at the red gmail dot com")
    assert profile is None and question == "Did you mean the Muhammad (…633) Chrome profile?"


def test_clear_winner_is_suggested_alone():
    # Like this PC: the …633 account is the "Muhammad" profile; "Umer" is a …634 account.
    profiles = [Profile("Default", "Muhammad", "xumer633@gmail.com"),
                Profile("Profile 5", "Umer", "amxyz634@gmail.com")]
    profile, question = resolve_profile(profiles, "xumar633 gmail com wale chrome")
    assert profile is None and question == "Did you mean the Muhammad (…633) Chrome profile?"
    assert "xumer633" not in question                       # full email never in the question


def test_unknown_profile_lists_options():
    profile, question = resolve_profile(PROFILES, "office")
    assert profile is None and "Muhammad" in question and "Umer" in question


def test_ambiguous_profile_asks():
    profiles = PROFILES + [Profile("Profile 6", "Umer Work", "umer.work@x.com")]
    assert len(find_profiles(profiles, "umer")) == 2
    profile, question = resolve_profile(profiles, "umer")
    assert profile is None and question.startswith("Which Chrome profile")


def skill(config, chrome_dir):
    config.settings["chrome"] = {"user_data_dir": str(chrome_dir)}
    return OpenChromeProfile(config)


def test_opens_profile_with_allowlisted_site(config, chrome_dir):
    with patch("assistant.skills.open_chrome_profile._launch") as launch:
        result = skill(config, chrome_dir).run(profile="Umer wala", site="youtube")
    launch.assert_called_once_with([r"C:\chrome.exe", "--profile-directory=Profile 5", "https://www.youtube.com"])
    assert result.ok and result.reply == "Opening youtube in the Umer profile."


def test_other_sites_become_google_search_only(config, chrome_dir):
    with patch("assistant.skills.open_chrome_profile._launch") as launch:
        skill(config, chrome_dir).run(profile="xumar633", site="https://evil.example.com")
    args = launch.call_args.args[0]
    assert args[2].startswith(GOOGLE_SEARCH) and ":" not in args[2][len(GOOGLE_SEARCH):]


def test_profile_without_site(config, chrome_dir):
    with patch("assistant.skills.open_chrome_profile._launch") as launch:
        result = skill(config, chrome_dir).run(profile="Saad")
    launch.assert_called_once_with([r"C:\chrome.exe", "--profile-directory=Profile 3"])
    assert result.reply == "Opening Chrome with the Saad profile."


def test_check_asks_before_launching(config, chrome_dir):
    s = skill(config, chrome_dir)
    ask = s.check(profile="I umar633x")
    assert ask.text == "Did you mean the Umer (…633) Chrome profile?" and ask.on_yes == {"profile": "Umer"}
    with patch("assistant.skills.open_chrome_profile._launch") as launch:
        assert not s.run(profile="I umar633x").ok
    launch.assert_not_called()
