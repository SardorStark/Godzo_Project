from __future__ import annotations

import pytest

from bot.config import load_config
from bot.models import RequiredChat


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
    assert config.required_chats == (
        RequiredChat(
            check_chat_id="@test1",
            join_url="https://t.me/test1",
            label="@test1",
        ),
        RequiredChat(
            check_chat_id="@test2",
            join_url="https://t.me/test2",
            label="@test2",
        ),
    )
    assert config.port == 8080


def test_load_config_requires_chats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com")
    monkeypatch.setenv("WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("REQUIRED_CHATS", "")

    with pytest.raises(ValueError):
        load_config()


def test_load_config_supports_private_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com")
    monkeypatch.setenv("WEBHOOK_SECRET", "secret")
    monkeypatch.setenv(
        "REQUIRED_CHATS",
        "-1001234567890|https://t.me/+abcd,@public_channel",
    )

    config = load_config()

    assert config.required_chats[0] == RequiredChat(
        check_chat_id="-1001234567890",
        join_url="https://t.me/+abcd",
        label="+abcd",
    )
    assert config.required_chats[1] == RequiredChat(
        check_chat_id="@public_channel",
        join_url="https://t.me/public_channel",
        label="@public_channel",
    )
