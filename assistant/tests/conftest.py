import pytest

from assistant.core.config import Config
from assistant.core.contacts import parse_contacts

# Fake people. "ali" is deliberately an alias of two contacts (the duplicate case).
TEST_CONTACTS = {
    "contacts": [
        {"name": "Ali Khan", "aliases": ["ali", "ali bhai"], "phone": "0300 1234567"},
        {"name": "Ali Raza", "aliases": ["ali"], "phone": "+92 333 7654321"},
        {"name": "Sara Ahmed", "aliases": ["sara", "sara baji"], "phone": "03211112222"},
        {"name": "Bad Number", "aliases": ["bad"], "phone": "12345"},
    ]
}


@pytest.fixture
def config() -> Config:
    return Config(
        settings={
            "assistant": {"name": "VisionX", "company": "VisionX Intelligence"},
            "brain": {"provider": "anthropic", "model": "claude-haiku-5-5", "effort": "low",
                      "api_key_env": "VISIONX_ANTHROPIC_KEY"},
        },
        apps={
            "chrome": {"aliases": ["google chrome", "browser"], "target": r"C:\chrome.exe"},
            "calculator": {"aliases": ["calc"], "target": "calculator:"},
            "whatsapp": {"aliases": ["whats app"], "target": "whatsapp:"},
        },
        websites={
            "youtube": {"aliases": ["you tube", "yt"], "url": "https://www.youtube.com"},
            "github": {"aliases": [], "url": "https://github.com"},
        },
        secrets={"VISIONX_ANTHROPIC_KEY": "test-key"},
        contacts=parse_contacts(TEST_CONTACTS),
    )
