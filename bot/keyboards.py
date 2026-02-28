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
            text="🚀 O'buna bo'lish",
            url=chat.join_url,
        )

    builder.button(text="✅ Tasdiqlash", callback_data="check_subs")
    # 2-column layout for channel buttons, last row is single "Tekshirish" button.
    pair_rows = [2] * (len(chats) // 2)
    if len(chats) % 2:
        pair_rows.append(1)
    pair_rows.append(1)
    builder.adjust(*pair_rows)
    return builder.as_markup()


def build_contact_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📲 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👥 Referal Linkim"),
                KeyboardButton(text="🪵 Qatnashuvchilar"),
            ],
            [
                KeyboardButton(text="👤 Profil"),
                KeyboardButton(text="🎁 Konkurs haqida"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def build_remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
