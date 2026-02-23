"""Inline keyboards used by the bot."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_subscription_keyboard(chats: Sequence[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for chat in chats:
        builder.button(
            text=f"Obuna bolish: {chat}",
            url=f"https://t.me/{chat.lstrip('@')}",
        )

    builder.button(text="Tekshirish", callback_data="check_subs")
    builder.adjust(1)
    return builder.as_markup()
