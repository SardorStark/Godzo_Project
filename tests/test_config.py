from __future__ import annotations

import pytest

from bot.config import load_config


def test_load_config_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com")
    monkeypatch.setenv("WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("REQUIRED_CHATS", "@test1,@test2")
    monkeypatch.setenv("PORT", "8080")

    config = load_config()

    assert config.bot_token == "token"
    assert config.webhook_base_url == "https://example.com"
    assert config.webhook_secret == "secret"
    assert config.required_chats == ("@test1", "@test2")
    assert config.port == 8080


def test_load_config_requires_chats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com")
    monkeypatch.setenv("WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("REQUIRED_CHATS", "")

    with pytest.raises(ValueError):
        load_config()
