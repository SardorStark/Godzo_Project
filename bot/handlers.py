"""Bot handlers for start, callback checks and fallback gate."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram import F, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards import build_subscription_keyboard
from bot.subscription import SubscriptionCheckError, is_subscribed

WELCOME_TEXT = "Obuna tasdiqlandi, xush kelibsiz!"
SUBSCRIPTION_REQUIRED_TEXT = (
    "Quyidagi kanallarga obuna boling va keyin Tekshirish tugmasini bosing."
)
SUBSCRIPTION_NOT_DONE_TEXT = "Hali barcha kanallarga obuna bolinmagan."
CHECK_ERROR_TEXT = "Tekshiruvda muammo, keyinroq urinib koring."
DEFAULT_SUBSCRIBED_TEXT = "Siz obuna bolgansiz. Hozircha /start dan foydalaning."


def setup_handlers(dispatcher: Dispatcher, required_chats: Sequence[str]) -> None:
    chats = tuple(required_chats)
    router = Router()

    async def send_subscription_prompt(message: Message, missing_chats: Sequence[str]) -> None:
        await message.answer(
            SUBSCRIPTION_REQUIRED_TEXT,
            reply_markup=build_subscription_keyboard(missing_chats),
        )

    async def check_user(message: Message) -> tuple[bool, list[str]] | None:
        if message.from_user is None:
            return None

        try:
            return await is_subscribed(
                bot=message.bot,
                user_id=message.from_user.id,
                required_chats=chats,
            )
        except SubscriptionCheckError:
            await message.answer(CHECK_ERROR_TEXT)
            return None

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        result = await check_user(message)
        if result is None:
            return

        is_user_subscribed, missing_chats = result
        if is_user_subscribed:
            await message.answer(WELCOME_TEXT)
            return

        await send_subscription_prompt(message, missing_chats)

    @router.callback_query(F.data == "check_subs")
    async def check_subs_handler(callback: CallbackQuery) -> None:
        if callback.message is None:
            await callback.answer()
            return

        try:
            is_user_subscribed, missing_chats = await is_subscribed(
                bot=callback.bot,
                user_id=callback.from_user.id,
                required_chats=chats,
            )
        except SubscriptionCheckError:
            await callback.answer(CHECK_ERROR_TEXT, show_alert=True)
            return

        if is_user_subscribed:
            await callback.message.edit_text(WELCOME_TEXT)
            await callback.answer("Tasdiqlandi")
            return

        await callback.message.edit_text(
            SUBSCRIPTION_REQUIRED_TEXT,
            reply_markup=build_subscription_keyboard(missing_chats),
        )
        await callback.answer(SUBSCRIPTION_NOT_DONE_TEXT)

    @router.message(F.text)
    async def gate_fallback_handler(message: Message) -> None:
        result = await check_user(message)
        if result is None:
            return

        is_user_subscribed, missing_chats = result
        if is_user_subscribed:
            await message.answer(DEFAULT_SUBSCRIBED_TEXT)
            return

        await send_subscription_prompt(message, missing_chats)

    dispatcher.include_router(router)
