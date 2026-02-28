"""Subscription check helpers."""

from __future__ import annotations

import logging
from typing import Sequence

from aiogram import Bot

from bot.models import RequiredChat

logger = logging.getLogger(__name__)

SUBSCRIBED_STATUSES = {"creator", "administrator", "member"}
UNSUBSCRIBED_STATUSES = {"left", "kicked", "restricted"}


class SubscriptionCheckError(Exception):
    """Raised when Telegram membership check fails unexpectedly."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


def is_member_status_subscribed(status: str) -> bool:
    if status in SUBSCRIBED_STATUSES:
        return True
    if status in UNSUBSCRIBED_STATUSES:
        return False
    return False


async def is_subscribed(
    bot: Bot, user_id: int, required_chats: Sequence[RequiredChat]
) -> tuple[bool, list[RequiredChat]]:
    missing_chats: list[RequiredChat] = []

    for chat in required_chats:
        try:
            member = await bot.get_chat_member(chat_id=chat.check_chat_id, user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Failed to check chat membership. user_id=%s chat=%s",
                user_id,
                chat.check_chat_id,
            )
            error_text = str(exc).lower()
            if "member list is inaccessible" in error_text:
                raise SubscriptionCheckError(
                    f"Obuna tekshiruv xatosi: {chat.label} kanalida bot admin emas "
                    "yoki a'zolar ro'yxati yopiq."
                ) from exc
            raise SubscriptionCheckError(
                f"Obuna tekshiruv xatosi: {chat.label} kanalini tekshirib bo'lmadi."
            ) from exc

        status = getattr(member.status, "value", str(member.status))
        if not is_member_status_subscribed(status):
            missing_chats.append(chat)

    return (len(missing_chats) == 0, missing_chats)
