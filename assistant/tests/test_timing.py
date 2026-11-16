from assistant.core.timing import Timings


def test_release_to_action_excludes_recording():
    t = Timings()
    t.add("rec", 2.0)
    t.add("stt", 0.5)
    t.add("brain", 0.8)
    t.add("skill", 0.1)
    assert round(t.release_to_action, 2) == 1.4
    assert t.as_dict()["release_to_action"] == 1.4
    assert "over 3s" not in t.summary()


def test_summary_flags_slow_commands():
    t = Timings()
    t.add("stt", 2.5)
    t.add("brain", 1.0)
    assert "over 3s target" in t.summary()


def test_step_context_manager():
    t = Timings()
    with t.step("brain"):
        pass
    assert "brain" in t.steps and Timings().summary() == ""
