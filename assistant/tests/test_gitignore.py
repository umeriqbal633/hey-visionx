import shutil
import subprocess

import pytest

from assistant.core.config import PROJECT_DIR

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def ignored(path: str) -> bool:
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=PROJECT_DIR)
    return result.returncode == 0


def test_private_files_are_ignored():
    assert ignored("assistant/config/contacts.yaml")
    assert ignored(".env")
    assert ignored("assistant/logs/actions.jsonl")


def test_example_files_are_not_ignored():
    assert not ignored("assistant/config/contacts.example.yaml")
    assert not ignored(".env.example")
