"""Bot handlers for registration, subscription check and referrals."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram import F, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

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


class RegistrationState(StatesGroup):
    waiting_contact = State()
    waiting_name = State()


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
        except SubscriptionCheckError as exc:
            await message.answer(exc.user_message or CHECK_ERROR_TEXT)
            return None

    async def send_after_subscribed_bundle(message: Message, user_id: int) -> None:
        record = await get_user_record(user_id)
        if record is None:
            return
        await message.answer(_contest_text(record), reply_markup=build_main_menu_keyboard())
        await message.answer(_profile_text(record), reply_markup=build_main_menu_keyboard())

    async def continue_after_registration(message: Message, state: FSMContext) -> None:
        result = await check_user(message)
        if result is None:
            return

        is_user_subscribed, missing_chats = result
        if is_user_subscribed:
            warned_users.discard(message.from_user.id if message.from_user else -1)
            await state.clear()
            if message.from_user is not None:
                await send_after_subscribed_bundle(message, message.from_user.id)
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
            existing = await get_user_record(message.from_user.id)
            if existing is not None and existing.participant_no > 0:
                await message.answer(
                    f"🎟 Sizning tartib raqamingiz: {existing.participant_no}",
                    reply_markup=build_main_menu_keyboard(),
                )
            await message.answer(ALREADY_REGISTERED_TEXT, reply_markup=build_main_menu_keyboard())
            await continue_after_registration(message, state)
            return

        referrer = _extract_referrer_user_id(message.text)
        await state.update_data(referrer_user_id=referrer)
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
        except SubscriptionCheckError as exc:
            await callback.answer(exc.user_message or CHECK_ERROR_TEXT, show_alert=True)
            return

        if is_user_subscribed:
            warned_users.discard(callback.from_user.id)
            await callback.message.edit_text("✅ Tasdiqlandi!")
            await send_after_subscribed_bundle(callback.message, callback.from_user.id)
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
        await message.answer(ASK_NAME_TEXT)

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
        )
        referrer = data.get("referrer_user_id")
        referrer_user_id = int(referrer) if isinstance(referrer, int) else None
        save_result = await save_registration(item, referrer_user_id=referrer_user_id)
        await state.clear()
        await message.answer(
            f"{REGISTERED_TEXT}\n🎟 Sizning tartib raqamingiz: {save_result.record.participant_no}",
            reply_markup=build_main_menu_keyboard(),
        )
        await continue_after_registration(message, state)

    @router.message(F.text == "👥 Referal Linkim")
    async def referral_link_handler(message: Message) -> None:
        if message.from_user is None:
            return
        record = await get_user_record(message.from_user.id)
        if record is None:
            await message.answer("⚠️ Avval /start bosib ro'yxatdan o'ting.")
            return
        link = await _build_referral_link(message, message.from_user.id)
        await message.answer(
            REFERRAL_TEXT_TEMPLATE.format(link=link, invites=record.invites_count),
            reply_markup=build_main_menu_keyboard(),
        )

    @router.message(F.text == "🪵 Qatnashuvchilar")
    async def participants_handler(message: Message) -> None:
        total = await get_total_participants()
        await message.answer(TOTAL_TEXT_TEMPLATE.format(total=total), reply_markup=build_main_menu_keyboard())

    @router.message(F.text == "👤 Profil")
    async def profile_handler(message: Message) -> None:
        if message.from_user is None:
            return
        record = await get_user_record(message.from_user.id)
        if record is None:
            await message.answer("⚠️ Avval /start bosib ro'yxatdan o'ting.")
            return
        await message.answer(_profile_text(record), reply_markup=build_main_menu_keyboard())

    @router.message(F.text == "🎁 Konkurs haqida")
    async def contest_info_handler(message: Message) -> None:
        await message.answer(CONTEST_RULES_TEXT, reply_markup=build_main_menu_keyboard())

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
            await message.answer("⚠️ Konkurs qayta boshlandi!\n\nQayta ishtirok etish uchun bosing! /start")
            return

        if message.from_user and await is_registered(message.from_user.id):
            if message.from_user.id not in warned_users:
                warned_users.add(message.from_user.id)
                await message.answer(UNSUBSCRIBED_WARNING_TEXT)
        await send_subscription_prompt(message, missing_chats)

    dispatcher.include_router(router)
