import pytest

from assistant.core.config import Config


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
    )
