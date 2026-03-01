"""Bot handlers for registration, subscription check and referrals."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from aiogram import F, Dispatcher, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ErrorEvent, Message

from bot.keyboards import (
    build_contact_request_keyboard,
    build_main_menu_keyboard,
    build_subscription_keyboard,
)
from bot.models import RequiredChat
from bot.storage import (
    UserRecord,
    UserRegistration,
    get_total_participants,
    get_user_record,
    is_registered,
    save_registration,
)
from bot.subscription import SubscriptionCheckError, is_subscribed

SUBSCRIPTION_REQUIRED_TEXT = (
    "🎟 Barcha kanallarga obuna bo'ling va konkurs ishtirokchisiga aylaning!\n\n"
    "✅ Kanallarga obuna bo'lganingizdan so'ng tasdiqlash tugmasini bosing."
)
SUBSCRIPTION_NOT_DONE_TEXT = "⚠️ Hali barcha kanallarga obuna bo'linmagan."
CHECK_ERROR_TEXT = "⚠️ Tekshiruvda muammo, keyinroq urinib ko'ring."
UNSUBSCRIBED_WARNING_TEXT = (
    "⚠️ Siz obunani uchirdingiz. Iltimos konkurs talablariga amal qiling."
)
ASK_CONTACT_TEXT = "📲 Botdan to'liq foydalanish uchun telefon raqamingizni yuboring."
ASK_NAME_TEXT = "✍️ Endi ism-familiyangizni yozing."
CONTACT_INVALID_TEXT = "📞 Telefon raqamni tugma orqali yuboring."
NAME_INVALID_TEXT = "❗ Ism juda qisqa. Qaytadan kiriting."
REGISTERED_TEXT = "✅ Malumot qabul qilindi."
ALREADY_REGISTERED_TEXT = "ℹ️ Siz oldin malumot topshirgansiz."
TOTAL_TEXT_TEMPLATE = "🪵 Jami qatnashuvchilar: {total}"
REFERRAL_TEXT_TEMPLATE = (
    "🔗 Sizning referal linkingiz:\n{link}\n\n"
    "👥 Taklif qilgan do'stlaringiz: {invites}\n"
    "🎁 Har 5 ta do'st uchun +1 ta qo'shimcha raqam beriladi."
)
CONTEST_RULES_TEXT = (
    "Bu Bot Orqali Siz🫵🏻\n"
    "Iphone 13 Pro Max 💰🤩\n"
    "8100 UC 🤑, Lednik full Akk 🎮\n"
    "Yoki 10 Ta Royal Pass 🎁\n"
    "Yutib Olishingiz Mumkin 🎉🏆\n\n"
    "Shartlarni bajarib O'z tartib raqamingizni oling ✅\n"
    "Har 5 ta do'stlaringizni taklif qilsangiz 🤔\n"
    "Yana qo'shimcha raqam beriladi 😱\n"
    "Bu esa yutishingiz ehtimolini oshiradi ✅"
)
PROCESSING_TEXT = "⏳ Tekshiruv ketmoqda, biroz kuting."

logger = logging.getLogger(__name__)


class RegistrationState(StatesGroup):
    waiting_contact = State()
    waiting_name = State()
    waiting_subscription = State()


def _extract_referrer_user_id(text: str | None) -> int | None:
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if not payload.startswith("ref_"):
        return None
    raw = payload[4:]
    return int(raw) if raw.isdigit() else None


async def _build_referral_link(message: Message, user_id: int) -> str:
    me = await message.bot.get_me()
    return f"https://t.me/{me.username}?start=ref_{user_id}"


def _bonus_numbers_text(record: UserRecord) -> str:
    numbers = [str(record.participant_no + i) for i in range(record.entries_count)]
    return ", ".join(numbers)


def _contest_text(record: UserRecord) -> str:
    return (
        "🎊 Tabriklaymiz! Siz GODZO konkursida ishtirokchisiz.\n\n"
        f"{CONTEST_RULES_TEXT}\n\n"
        f"🎟 Sizning raqamingiz: {record.participant_no}\n\n"
        "•┈┈┈┈••✦❀✦••┈┈┈┈•\n"
        "⚠️ • Eslatma! Homiy kanallardan chiqib ketsangiz, bot sizni qoida buzar deb "
        "hisoblaydi va konkursimizdan chetlashtiradi.\n\n"
        "🔗 • Sizga berilgan Referal link orqali, botimizga 5 ta do'stingizni taklif qilib "
        "qo'shimcha raqam olishingiz mumkin. Bu esa yutish imkonini yanada oshiradi.\n\n"
        "🗓 • G'oliblar tez orada GODZO youtube strimida random tarzda aniqlanadi va "
        "hammaga e'lon qilinadi! Kanalimizni kuzatishda davom eting!"
    )


def _profile_text(record: UserRecord) -> str:
    return (
        "🆔👤 Sizning profilingiz.\n\n"
        f"🎟 Sizning raqamingiz: {record.participant_no}\n\n"
        f"💈 Sizning bonus raqamlaringiz: {_bonus_numbers_text(record)}\n"
        f"💁🏻‍♂️ 🔗 Referallar soni: {record.invites_count}"
    )


def setup_handlers(dispatcher: Dispatcher, required_chats: Sequence[RequiredChat]) -> None:
    chats = tuple(required_chats)
    router = Router()
    warned_users: set[int] = set()
    confirmed_subscribers: set[int] = set()
    processing_checks: set[int] = set()

    async def safe_answer(message: Message, text: str, **kwargs) -> None:
        try:
            await message.answer(text, **kwargs)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send message to user_id=%s", getattr(message.from_user, "id", None))

    async def safe_edit_or_answer(
        callback: CallbackQuery, text: str, **kwargs
    ) -> None:
        if callback.message is None:
            return
        try:
            await callback.message.edit_text(text, **kwargs)
            return
        except TelegramBadRequest:
            # Message can be not editable, old, or unchanged; fallback to sending a new message.
            logger.warning("edit_text failed, fallback to answer. user_id=%s", callback.from_user.id)
        except TelegramAPIError:
            logger.exception("Unexpected Telegram API error on edit_text. user_id=%s", callback.from_user.id)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error on edit_text. user_id=%s", callback.from_user.id)
        await safe_answer(callback.message, text, **kwargs)

    async def send_subscription_prompt(
        message: Message, missing_chats: Sequence[RequiredChat]
    ) -> None:
        await safe_answer(
            message,
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
        except SubscriptionCheckError as exc:
            await safe_answer(message, exc.user_message or CHECK_ERROR_TEXT)
            return None

    async def send_after_subscribed_bundle(message: Message, user_id: int) -> None:
        record = await get_user_record(user_id)
        if record is None:
            return
        await safe_answer(message, _contest_text(record), reply_markup=build_main_menu_keyboard())
        await safe_answer(message, _profile_text(record), reply_markup=build_main_menu_keyboard())

    async def finalize_registration_if_ready(message: Message, state: FSMContext) -> bool:
        if message.from_user is None:
            return False
        if await is_registered(message.from_user.id):
            return True

        data = await state.get_data()
        if not data.get("registration_ready", False):
            await safe_answer(message, "❗ Avval /start orqali ro'yxatdan o'ting.")
            return False

        item = UserRegistration(
            user_id=message.from_user.id,
            username=message.from_user.username or "",
        )
        referrer = data.get("referrer_user_id")
        referrer_user_id = int(referrer) if isinstance(referrer, int) else None
        save_result = await save_registration(item, referrer_user_id=referrer_user_id)
        await state.clear()
        await safe_answer(
            message,
            f"🎟 Sizning tartib raqamingiz: {save_result.record.participant_no}",
            reply_markup=build_main_menu_keyboard(),
        )
        return True

    async def continue_after_registration(message: Message, state: FSMContext) -> None:
        result = await check_user(message)
        if result is None:
            return

        is_user_subscribed, missing_chats = result
        if is_user_subscribed:
            if message.from_user is not None:
                confirmed_subscribers.add(message.from_user.id)
            warned_users.discard(message.from_user.id if message.from_user else -1)
            await state.clear()
            if message.from_user is not None:
                await send_after_subscribed_bundle(message, message.from_user.id)
            return

        if message.from_user and await is_registered(message.from_user.id):
            if (
                message.from_user.id in confirmed_subscribers
                and message.from_user.id not in warned_users
            ):
                warned_users.add(message.from_user.id)
                await safe_answer(message, UNSUBSCRIBED_WARNING_TEXT)
        await send_subscription_prompt(message, missing_chats)

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            return

        if await is_registered(message.from_user.id):
            await safe_answer(message, ALREADY_REGISTERED_TEXT, reply_markup=build_main_menu_keyboard())
            await continue_after_registration(message, state)
            return

        referrer = _extract_referrer_user_id(message.text)
        await state.update_data(referrer_user_id=referrer)
        await state.set_state(RegistrationState.waiting_contact)
        await safe_answer(
            message,
            ASK_CONTACT_TEXT,
            reply_markup=build_contact_request_keyboard(),
        )

    @router.callback_query(F.data == "check_subs")
    async def check_subs_handler(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.message is None:
            await callback.answer()
            return
        if callback.from_user.id in processing_checks:
            await callback.answer(PROCESSING_TEXT)
            return
        processing_checks.add(callback.from_user.id)

        try:
            try:
                is_user_subscribed, missing_chats = await is_subscribed(
                    bot=callback.bot,
                    user_id=callback.from_user.id,
                    required_chats=chats,
                )
            except SubscriptionCheckError as exc:
                await callback.answer(exc.user_message or CHECK_ERROR_TEXT, show_alert=True)
                return

            if is_user_subscribed:
                if not await is_registered(callback.from_user.id):
                    finalized = await finalize_registration_if_ready(callback.message, state)
                    if not finalized:
                        warned_users.discard(callback.from_user.id)
                        await safe_edit_or_answer(callback, "✅ Obuna tasdiqlandi!")
                        await safe_answer(
                            callback.message,
                            "❗ Raqam olish uchun avval ro'yxatdan o'ting: /start"
                        )
                        await callback.answer("Avval ro'yxatdan o'ting")
                        return
                confirmed_subscribers.add(callback.from_user.id)
                warned_users.discard(callback.from_user.id)
                await safe_edit_or_answer(callback, "✅ Tasdiqlandi!")
                await send_after_subscribed_bundle(callback.message, callback.from_user.id)
                await callback.answer("Tasdiqlandi")
                return

            if await is_registered(callback.from_user.id):
                if (
                    callback.from_user.id in confirmed_subscribers
                    and callback.from_user.id not in warned_users
                ):
                    warned_users.add(callback.from_user.id)
                    await safe_answer(callback.message, UNSUBSCRIBED_WARNING_TEXT)
            await safe_edit_or_answer(
                callback,
                SUBSCRIPTION_REQUIRED_TEXT,
                reply_markup=build_subscription_keyboard(missing_chats),
            )
            await callback.answer(SUBSCRIPTION_NOT_DONE_TEXT)
        finally:
            processing_checks.discard(callback.from_user.id)

    @router.message(RegistrationState.waiting_contact, F.contact)
    async def contact_handler(message: Message, state: FSMContext) -> None:
        if message.contact is None:
            return
        if (
            message.from_user is not None
            and message.contact.user_id is not None
            and message.contact.user_id != message.from_user.id
        ):
            await safe_answer(message, "❗ Iltimos, faqat o'zingizning raqamingizni yuboring.")
            return
        await state.update_data(phone_number=message.contact.phone_number)
        await state.set_state(RegistrationState.waiting_name)
        await safe_answer(message, ASK_NAME_TEXT)

    @router.message(RegistrationState.waiting_contact)
    async def contact_invalid_handler(message: Message) -> None:
        await safe_answer(message, CONTACT_INVALID_TEXT, reply_markup=build_contact_request_keyboard())

    @router.message(RegistrationState.waiting_name, F.text)
    async def name_handler(message: Message, state: FSMContext) -> None:
        if message.from_user is None or message.text is None:
            return
        entered_name = message.text.strip()
        if len(entered_name) < 2:
            await safe_answer(message, NAME_INVALID_TEXT)
            return

        data = await state.get_data()
        phone = str(data.get("phone_number", "")).strip()
        if not phone:
            await state.set_state(RegistrationState.waiting_contact)
            await safe_answer(
                message,
                ASK_CONTACT_TEXT,
                reply_markup=build_contact_request_keyboard(),
            )
            return

        await state.update_data(registration_ready=True)
        await state.set_state(RegistrationState.waiting_subscription)
        await safe_answer(
            message,
            f"{REGISTERED_TEXT}\n✅ Endi obunani tasdiqlang.",
            reply_markup=build_main_menu_keyboard(),
        )
        result = await check_user(message)
        if result is None:
            return
        is_user_subscribed, missing_chats = result
        if is_user_subscribed:
            finalized = await finalize_registration_if_ready(message, state)
            if finalized and message.from_user is not None:
                confirmed_subscribers.add(message.from_user.id)
                warned_users.discard(message.from_user.id)
                await send_after_subscribed_bundle(message, message.from_user.id)
            return
        await send_subscription_prompt(message, missing_chats)

    @router.message(F.text == "👥 Referal Linkim")
    async def referral_link_handler(message: Message) -> None:
        if message.from_user is None:
            return
        record = await get_user_record(message.from_user.id)
        if record is None:
            await safe_answer(message, "⚠️ Avval /start bosib ro'yxatdan o'ting.")
            return
        link = await _build_referral_link(message, message.from_user.id)
        await safe_answer(
            message,
            REFERRAL_TEXT_TEMPLATE.format(link=link, invites=record.invites_count),
            reply_markup=build_main_menu_keyboard(),
        )

    @router.message(F.text == "🪵 Qatnashuvchilar")
    async def participants_handler(message: Message) -> None:
        total = await get_total_participants()
        await safe_answer(
            message,
            TOTAL_TEXT_TEMPLATE.format(total=total),
            reply_markup=build_main_menu_keyboard(),
        )

    @router.message(F.text == "👤 Profil")
    async def profile_handler(message: Message) -> None:
        if message.from_user is None:
            return
        record = await get_user_record(message.from_user.id)
        if record is None:
            await safe_answer(message, "⚠️ Avval /start bosib ro'yxatdan o'ting.")
            return
        await safe_answer(message, _profile_text(record), reply_markup=build_main_menu_keyboard())

    @router.message(F.text == "🎁 Konkurs haqida")
    async def contest_info_handler(message: Message) -> None:
        await safe_answer(message, CONTEST_RULES_TEXT, reply_markup=build_main_menu_keyboard())

    @router.message(F.text)
    async def gate_fallback_handler(message: Message, state: FSMContext) -> None:
        current_state = await state.get_state()
        if current_state == RegistrationState.waiting_contact.state:
            await safe_answer(message, CONTACT_INVALID_TEXT, reply_markup=build_contact_request_keyboard())
            return
        if current_state == RegistrationState.waiting_name.state:
            await safe_answer(message, NAME_INVALID_TEXT)
            return
        if current_state == RegistrationState.waiting_subscription.state:
            result = await check_user(message)
            if result is None:
                return
            is_user_subscribed, missing_chats = result
            if is_user_subscribed:
                finalized = await finalize_registration_if_ready(message, state)
                if finalized and message.from_user is not None:
                    confirmed_subscribers.add(message.from_user.id)
                    warned_users.discard(message.from_user.id)
                    await send_after_subscribed_bundle(message, message.from_user.id)
                return
            await send_subscription_prompt(message, missing_chats)
            return

        result = await check_user(message)
        if result is None:
            return

        is_user_subscribed, missing_chats = result
        if is_user_subscribed:
            if message.from_user is not None:
                confirmed_subscribers.add(message.from_user.id)
            warned_users.discard(message.from_user.id if message.from_user else -1)
            await safe_answer(
                message,
                "⚠️ Konkurs qayta boshlandi!\n\nQayta ishtirok etish uchun bosing! /start",
            )
            return

        if message.from_user and await is_registered(message.from_user.id):
            if (
                message.from_user.id in confirmed_subscribers
                and message.from_user.id not in warned_users
            ):
                warned_users.add(message.from_user.id)
                await safe_answer(message, UNSUBSCRIBED_WARNING_TEXT)
        await send_subscription_prompt(message, missing_chats)

    @router.error()
    async def global_error_handler(event: ErrorEvent) -> bool:
        logger.exception("Unhandled bot error", exc_info=event.exception)
        update = event.update
        cb = getattr(update, "callback_query", None)
        msg = getattr(update, "message", None)
        target = msg if msg is not None else getattr(cb, "message", None)
        if target is not None and hasattr(target, "answer"):
            await safe_answer(target, CHECK_ERROR_TEXT, reply_markup=build_main_menu_keyboard())
        if cb is not None:
            try:
                await cb.answer("Xatolik yuz berdi, qayta urinib ko'ring.", show_alert=True)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to answer callback on error.")
        return True

    dispatcher.include_router(router)
