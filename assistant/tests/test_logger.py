import json

from assistant.core.logger import ActionLogger


def test_appends_jsonl(tmp_path):
    path = tmp_path / "logs" / "actions.jsonl"
    logger = ActionLogger(path)
    logger.log(command="chrome kholo", skill="open_app", params={"app": "chrome"},
               confirmed=None, ok=True, reply="Opening chrome.")
    logger.log(command="message bhejo", skill="send_whatsapp", params={},
               confirmed=False, ok=False, reply="Okay, cancelled.")

    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    first = lines[0]
    assert set(first) == {"timestamp", "command", "skill", "params", "confirmed", "ok", "reply"}
    assert first["command"] == "chrome kholo" and first["confirmed"] is None
    assert lines[1]["confirmed"] is False


def test_keeps_urdu_readable(tmp_path):
    path = tmp_path / "a.jsonl"
    ActionLogger(path).log(command="کروم کھولو", skill=None, params=None,
                           confirmed=None, ok=True, reply="x")
    assert "کروم کھولو" in path.read_text(encoding="utf-8")
