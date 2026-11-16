from datetime import datetime
from unittest.mock import patch

from assistant.skills.get_time import GetTime


def test_reports_time_and_date(config):
    fixed = datetime(2026, 11, 17, 9, 5)
    with patch("assistant.skills.get_time._now", return_value=fixed):
        result = GetTime(config).run()
    assert result.ok
    assert result.reply == "It's 9:05 AM on Tuesday, 17 November."


def test_afternoon(config):
    with patch("assistant.skills.get_time._now", return_value=datetime(2026, 11, 17, 15, 45)):
        assert "3:45 PM" in GetTime(config).run().reply
