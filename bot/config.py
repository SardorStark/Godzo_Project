"""Environment configuration for the bot."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

from bot.models import RequiredChat


@dataclass(frozen=True)
class Config:
    bot_token: str
    webhook_base_url: str
    webhook_secret: str
    required_chats: tuple[RequiredChat, ...]
    port: int


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


_CHAT_ID_PATTERN = re.compile(r"^-100\d{5,}$")


def _is_chat_id(value: str) -> bool:
    return bool(_CHAT_ID_PATTERN.match(value))


def _normalize_tg_link(value: str) -> str | None:
    if value.startswith("https://t.me/"):
        return value
    if value.startswith("http://t.me/"):
        return "https://" + value[len("http://") :]
    return None


def _parse_chat_item(raw_item: str) -> RequiredChat:
    item = raw_item.strip()
    if not item:
        raise ValueError("REQUIRED_CHATS contains an empty item")

    if "|" in item:
        left, right = item.split("|", 1)
        check_id = left.strip()
        join_link = right.strip()
        if not _is_chat_id(check_id):
            raise ValueError(
                "When using 'chat_id|invite_link', chat_id must look like -100... "
                f"Invalid item: {raw_item}"
            )
        normalized_link = _normalize_tg_link(join_link)
        if normalized_link is None:
            raise ValueError(
                "Invite link must start with https://t.me/ when using chat_id|link. "
                f"Invalid item: {raw_item}"
            )
        return RequiredChat(
            check_chat_id=check_id,
            join_url=normalized_link,
            label=normalized_link.rsplit("/", 1)[-1],
        )

    if item.startswith("@"):
        username = item
        return RequiredChat(
            check_chat_id=username,
            join_url=f"https://t.me/{username.lstrip('@')}",
            label=username,
        )

    normalized_link = _normalize_tg_link(item)
    if normalized_link is not None:
        suffix = normalized_link.rsplit("/", 1)[-1]
        if suffix.startswith("+"):
            raise ValueError(
                "Private invite links require chat_id mapping. Use format "
                "'-1001234567890|https://t.me/+invite'. "
                f"Invalid item: {raw_item}"
            )
        username = f"@{suffix}"
        return RequiredChat(
            check_chat_id=username,
            join_url=normalized_link,
            label=username,
        )

    if _is_chat_id(item):
        raise ValueError(
            "Private chat ID requires join link for keyboard. Use format "
            "'-1001234567890|https://t.me/+invite'. "
            f"Invalid item: {raw_item}"
        )

    raise ValueError(
        "Invalid REQUIRED_CHATS item. Supported: @username, https://t.me/username, "
        "or -100...|https://t.me/+invite. "
        f"Invalid item: {raw_item}"
    )


def _parse_required_chats(raw_value: str) -> tuple[RequiredChat, ...]:
    items = [part.strip() for part in raw_value.split(",") if part.strip()]
    if not items:
        raise ValueError("REQUIRED_CHATS must contain at least one chat item")
    return tuple(_parse_chat_item(item) for item in items)


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
