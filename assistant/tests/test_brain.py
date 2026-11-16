from assistant.core.brain import Brain
from assistant.core.providers.base import BrainError, Provider, ProviderResponse
from assistant.core.registry import discover


class FakeProvider(Provider):
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def choose(self, system, tools, command):
        self.calls.append((system, tools, command))
        if self.error:
            raise self.error
        return self.response


def test_tool_call_becomes_decision(config):
    p = FakeProvider(ProviderResponse(tool_name="open_app", tool_input={"app": "chrome"}))
    d = Brain(p, discover(config)).decide("chrome kholo")
    assert d.skill == "open_app" and d.params == {"app": "chrome"} and d.reply is None


def test_text_reply_passes_through(config):
    p = FakeProvider(ProviderResponse(text="Kaunsi app?"))
    d = Brain(p, discover(config)).decide("kholo")
    assert d.skill is None and d.reply == "Kaunsi app?"


def test_unknown_tool_name_is_rejected(config):
    p = FakeProvider(ProviderResponse(tool_name="run_shell", tool_input={"cmd": "del *"}))
    d = Brain(p, discover(config)).decide("x")
    assert d.skill is None and d.reply


def test_provider_error_becomes_reply(config):
    p = FakeProvider(error=BrainError("I'm being rate limited right now."))
    d = Brain(p, discover(config)).decide("x")
    assert d.reply == "I'm being rate limited right now."


def test_system_prompt_is_stable_and_named(config):
    p = FakeProvider(ProviderResponse(text="ok"))
    brain = Brain(p, discover(config), "VisionX", "VisionX Intelligence")
    brain.decide("a")
    brain.decide("b")
    (s1, t1, _), (s2, t2, _) = p.calls
    assert s1 == s2 and t1 == t2                      # byte-identical prefix for caching
    assert "VisionX" in s1 and "Roman Urdu" in s1
