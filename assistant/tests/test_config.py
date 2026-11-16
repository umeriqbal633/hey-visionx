import os

from assistant.core.config import CONFIG_DIR, load_config


def test_env_file_is_not_copied_into_os_environ(tmp_path, monkeypatch):
    monkeypatch.delenv("VISIONX_ANTHROPIC_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("VISIONX_ANTHROPIC_KEY=secret-123\n", encoding="utf-8")

    config = load_config(CONFIG_DIR, env)

    assert config.secret("VISIONX_ANTHROPIC_KEY") == "secret-123"
    assert "VISIONX_ANTHROPIC_KEY" not in os.environ   # child processes won't inherit it


def test_real_config_files_load():
    config = load_config(CONFIG_DIR, CONFIG_DIR / "missing.env")
    assert config.assistant_name == "VisionX"
    assert config.brain["model"] == "claude-haiku-5-5"
    assert config.brain["api_key_env"] != "ANTHROPIC_API_KEY"
    for name in ("chrome", "whatsapp", "file explorer", "calculator"):
        assert name in config.apps and config.apps[name]["target"]
    for site in config.websites.values():
        assert site["url"].startswith("https://")
