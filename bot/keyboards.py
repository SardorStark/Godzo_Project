"""Keyboards used by the bot."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.models import RequiredChat


def build_subscription_keyboard(chats: Sequence[RequiredChat]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for chat in chats:
        builder.button(
            text=f"Obuna bolish: {chat.label}",
            url=chat.join_url,
        )

    builder.button(text="Tekshirish", callback_data="check_subs")
    builder.adjust(1)
    return builder.as_markup()


def build_contact_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
