"""Environment configuration for the bot."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    webhook_base_url: str
    webhook_secret: str
    required_chats: tuple[str, ...]
    port: int


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _parse_required_chats(raw_value: str) -> tuple[str, ...]:
    chats = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    if not chats:
        raise ValueError("REQUIRED_CHATS must contain at least one chat username")

    invalid = [chat for chat in chats if not chat.startswith("@")]
    if invalid:
        raise ValueError(
            "Each REQUIRED_CHATS item must start with '@'. Invalid: "
            + ", ".join(invalid)
        )
    return chats


def _parse_port(raw_value: str) -> int:
    try:
        port = int(raw_value)
    except ValueError as exc:
        raise ValueError("PORT must be an integer") from exc

    if port <= 0 or port > 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return port


def load_config() -> Config:
    load_dotenv()

    bot_token = _require_env("BOT_TOKEN")
    webhook_base_url = _require_env("WEBHOOK_BASE_URL").rstrip("/")
    webhook_secret = _require_env("WEBHOOK_SECRET")
    required_chats = _parse_required_chats(_require_env("REQUIRED_CHATS"))
    port = _parse_port(os.getenv("PORT", "8080"))

    if not webhook_base_url.startswith(("https://", "http://")):
        raise ValueError("WEBHOOK_BASE_URL must start with https:// or http://")

    return Config(
        bot_token=bot_token,
        webhook_base_url=webhook_base_url,
        webhook_secret=webhook_secret,
        required_chats=required_chats,
        port=port,
    )
