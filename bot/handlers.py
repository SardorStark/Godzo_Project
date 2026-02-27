"""Bot handlers for start, callback checks and fallback gate."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram import F, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    build_contact_request_keyboard,
    build_remove_keyboard,
    build_subscription_keyboard,
)
from bot.models import RequiredChat
from bot.storage import UserRegistration, is_registered, save_registration
from bot.subscription import SubscriptionCheckError, is_subscribed

WELCOME_TEXT = "Obuna tasdiqlandi, xush kelibsiz!"
SUBSCRIPTION_REQUIRED_TEXT = (
    "Quyidagi kanallarga obuna boling va keyin Tekshirish tugmasini bosing."
)
SUBSCRIPTION_NOT_DONE_TEXT = "Hali barcha kanallarga obuna bolinmagan."
CHECK_ERROR_TEXT = "Tekshiruvda muammo, keyinroq urinib koring."
UNSUBSCRIBED_WARNING_TEXT = (
    "Siz obunani uchirdingiz. Iltimos konkurs talablariga amal qiling."
)
DEFAULT_SUBSCRIBED_TEXT = "Siz obuna bolgansiz. Hozircha /start dan foydalaning."
ASK_CONTACT_TEXT = "Davom etish uchun telefon raqamingizni yuboring."
ASK_NAME_TEXT = "Endi ism-familiyangizni yozing."
CONTACT_INVALID_TEXT = "Telefon raqamni tugma orqali yuboring."
NAME_INVALID_TEXT = "Ism juda qisqa. Qaytadan kiriting."
REGISTERED_TEXT = "Malumot qabul qilindi."
ALREADY_REGISTERED_TEXT = "Siz oldin malumot topshirgansiz."
PROMO_TEXT_TEMPLATE = "Sizning promo kodingiz: {promo_code}"


class RegistrationState(StatesGroup):
    waiting_contact = State()
    waiting_name = State()


def build_promo_code(user_id: int) -> str:
    return f"GODZO{user_id % 1_000_000:06d}"


def setup_handlers(dispatcher: Dispatcher, required_chats: Sequence[RequiredChat]) -> None:
    chats = tuple(required_chats)
    router = Router()
    warned_users: set[int] = set()

    async def send_subscription_prompt(
        message: Message, missing_chats: Sequence[RequiredChat]
    ) -> None:
        await message.answer(
            SUBSCRIPTION_REQUIRED_TEXT,
            reply_markup=build_subscription_keyboard(missing_chats),
        )

    async def check_user(message: Message) -> tuple[bool, list[RequiredChat]] | None:
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

    async def continue_after_registration(message: Message, state: FSMContext) -> None:
        result = await check_user(message)
        if result is None:
            return

        is_user_subscribed, missing_chats = result
        if is_user_subscribed:
            warned_users.discard(message.from_user.id if message.from_user else -1)
            await state.clear()
            await message.answer(WELCOME_TEXT, reply_markup=build_remove_keyboard())
            if message.from_user is not None:
                await message.answer(
                    PROMO_TEXT_TEMPLATE.format(
                        promo_code=build_promo_code(message.from_user.id)
                    )
                )
            return

        if message.from_user and await is_registered(message.from_user.id):
            if message.from_user.id not in warned_users:
                warned_users.add(message.from_user.id)
                await message.answer(UNSUBSCRIBED_WARNING_TEXT)
        await send_subscription_prompt(message, missing_chats)

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            return

        if await is_registered(message.from_user.id):
            await message.answer(ALREADY_REGISTERED_TEXT, reply_markup=build_remove_keyboard())
            await continue_after_registration(message, state)
            return

        await state.set_state(RegistrationState.waiting_contact)
        await message.answer(
            ASK_CONTACT_TEXT,
            reply_markup=build_contact_request_keyboard(),
        )

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
            warned_users.discard(callback.from_user.id)
            await callback.message.edit_text(WELCOME_TEXT)
            await callback.message.answer(
                PROMO_TEXT_TEMPLATE.format(
                    promo_code=build_promo_code(callback.from_user.id)
                ),
                reply_markup=build_remove_keyboard(),
            )
            await callback.answer("Tasdiqlandi")
            return

        if await is_registered(callback.from_user.id):
            if callback.from_user.id not in warned_users:
                warned_users.add(callback.from_user.id)
                await callback.message.answer(UNSUBSCRIBED_WARNING_TEXT)
        await callback.message.edit_text(
            SUBSCRIPTION_REQUIRED_TEXT,
            reply_markup=build_subscription_keyboard(missing_chats),
        )
        await callback.answer(SUBSCRIPTION_NOT_DONE_TEXT)

    @router.message(RegistrationState.waiting_contact, F.contact)
    async def contact_handler(message: Message, state: FSMContext) -> None:
        if message.contact is None:
            return
        await state.update_data(phone_number=message.contact.phone_number)
        await state.set_state(RegistrationState.waiting_name)
        await message.answer(ASK_NAME_TEXT, reply_markup=build_remove_keyboard())

    @router.message(RegistrationState.waiting_contact)
    async def contact_invalid_handler(message: Message) -> None:
        await message.answer(CONTACT_INVALID_TEXT, reply_markup=build_contact_request_keyboard())

    @router.message(RegistrationState.waiting_name, F.text)
    async def name_handler(message: Message, state: FSMContext) -> None:
        if message.from_user is None or message.text is None:
            return
        entered_name = message.text.strip()
        if len(entered_name) < 2:
            await message.answer(NAME_INVALID_TEXT)
            return

        data = await state.get_data()
        phone = str(data.get("phone_number", "")).strip()
        if not phone:
            await state.set_state(RegistrationState.waiting_contact)
            await message.answer(
                ASK_CONTACT_TEXT,
                reply_markup=build_contact_request_keyboard(),
            )
            return

        item = UserRegistration(
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            full_name=message.from_user.full_name,
            phone_number=phone,
            entered_name=entered_name,
        )
        await save_registration(item)
        await state.clear()
        await message.answer(REGISTERED_TEXT, reply_markup=build_remove_keyboard())
        await continue_after_registration(message, state)

    @router.message(F.text)
    async def gate_fallback_handler(message: Message, state: FSMContext) -> None:
        current_state = await state.get_state()
        if current_state == RegistrationState.waiting_contact.state:
            await message.answer(CONTACT_INVALID_TEXT, reply_markup=build_contact_request_keyboard())
            return
        if current_state == RegistrationState.waiting_name.state:
            await message.answer(NAME_INVALID_TEXT)
            return

        result = await check_user(message)
        if result is None:
            return

        is_user_subscribed, missing_chats = result
        if is_user_subscribed:
            warned_users.discard(message.from_user.id if message.from_user else -1)
            await message.answer(DEFAULT_SUBSCRIBED_TEXT)
            if message.from_user is not None:
                await message.answer(
                    PROMO_TEXT_TEMPLATE.format(
                        promo_code=build_promo_code(message.from_user.id)
                    )
                )
            return

        if message.from_user and await is_registered(message.from_user.id):
            if message.from_user.id not in warned_users:
                warned_users.add(message.from_user.id)
                await message.answer(UNSUBSCRIBED_WARNING_TEXT)
        await send_subscription_prompt(message, missing_chats)

    dispatcher.include_router(router)
