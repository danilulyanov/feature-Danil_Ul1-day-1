from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.keyboards import preferences_keyboard
from bot.handlers.profile.states import EditPreferences
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger

logger = get_logger(__name__)
router = Router()


async def _prepare_preferences_view(tg_id: str, fallback_lang: str | None = None):
    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(user.language_code if user and user.language_code else fallback_lang)

    if not user:
        return None, lang, None, None

    prefs = user.preferences or {}
    lang_name = t(f"profile.languages.{lang}", lang)
    schedule_time = prefs.get("vacancy_schedule_time") or t("profile.not_set", lang)
    text = t("profile.preferences_view", lang).format(language=lang_name, vacancy_time=schedule_time)
    markup = preferences_keyboard(False, lang)
    return user, lang, text, markup


async def send_preferences_view(message_obj: types.Message | types.CallbackQuery, tg_id: str, edit: bool = False):
    user, lang, text, markup = await _prepare_preferences_view(
        tg_id,
        message_obj.from_user.language_code if message_obj.from_user else None,
    )
    if not user:
        target = message_obj.message if isinstance(message_obj, types.CallbackQuery) else message_obj
        await target.answer(t("profile.no_profile", lang))
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()
        return

    target = message_obj.message if isinstance(message_obj, types.CallbackQuery) else message_obj
    if isinstance(message_obj, types.CallbackQuery) and edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await message_obj.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()


@router.message(Command("preferences"))
async def cmd_preferences(message: types.Message):
    await send_preferences_view(message, str(message.from_user.id))


@router.callback_query(F.data == "prefs_menu")
async def cb_prefs_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_preferences_view(call, str(call.from_user.id), edit=True)


@router.callback_query(F.data == "prefs_schedule_time")
async def cb_prefs_schedule_time(call: types.CallbackQuery, state: FSMContext):
    tg_id = str(call.from_user.id)
    user, lang, _, _ = await _prepare_preferences_view(tg_id, call.from_user.language_code if call.from_user else None)
    if not user:
        await call.message.answer(t("profile.no_profile", lang))
        await call.answer()
        return

    prompt = await call.message.answer(t("profile.preferences_schedule_prompt", lang))
    await state.set_state(EditPreferences.schedule_time)
    await state.update_data(
        prefs_message_id=call.message.message_id,
        prefs_chat_id=call.message.chat.id,
        prompt_message_id=prompt.message_id,
    )
    await call.answer()


@router.callback_query(F.data == "prefs_back_profile")
async def cb_prefs_back_profile(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    from bot.handlers.profile.view import send_profile_view

    await send_profile_view(str(call.from_user.id), call.message, edit=True)
    await call.answer()


@router.callback_query(F.data == "prefs_lang_menu")
async def cb_prefs_lang_menu(call: types.CallbackQuery, state: FSMContext):
    lang = detect_lang(call.from_user.language_code if call.from_user else None)
    buttons = [
        [types.InlineKeyboardButton(text=t("profile.languages.en", lang), callback_data="prefs_set_lang:en")],
        [types.InlineKeyboardButton(text=t("profile.languages.ru", lang), callback_data="prefs_set_lang:ru")],
        [types.InlineKeyboardButton(text=t("profile.buttons.back_profile", lang), callback_data="prefs_menu")],
    ]
    await call.message.answer(
        t("profile.preferences_lang_prompt", lang), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.clear()
    await call.answer()


@router.callback_query(F.data.startswith("prefs_set_lang:"))
async def cb_prefs_set_lang(call: types.CallbackQuery, state: FSMContext):
    _, _, code = call.data.partition(":")
    if code not in {"en", "ru"}:
        lang = detect_lang(call.from_user.language_code if call.from_user else None)
        await call.message.answer(t("profile.preferences_lang_invalid", lang))
        await call.answer()
        return

    target_lang = detect_lang(code)
    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_language_code(str(call.from_user.id), target_lang)

    lang_name = t(f"profile.languages.{target_lang}", target_lang)
    await call.message.answer(t("profile.preferences_lang_saved", target_lang).format(language=lang_name))
    await call.answer()
    await send_preferences_view(call, str(call.from_user.id), edit=True)


def _parse_time(raw: str) -> str | None:
    parts = raw.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    hours, minutes = parts
    hour_int, minute_int = int(hours), int(minutes)
    if not (0 <= hour_int <= 23 and 0 <= minute_int <= 59):
        return None
    return f"{hour_int:02d}:{minute_int:02d}"


@router.message(EditPreferences.schedule_time)
async def save_schedule_time(message: types.Message, state: FSMContext):
    raw = (message.text or "").strip()
    user_id = str(message.from_user.id)
    _, lang, _, _ = await _prepare_preferences_view(
        user_id, message.from_user.language_code if message.from_user else None
    )
    lowered = raw.lower()
    if lowered in {"clear", "none", "null", "удалить", "сбросить"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_preferences(user_id, vacancy_schedule_time=None)
        confirmation = await message.answer(t("profile.preferences_schedule_cleared", lang))
        await _cleanup_schedule_messages(message, confirmation, state)
        await _refresh_preferences_message(message, user_id, state)
        await state.clear()
        return

    parsed = _parse_time(raw)
    if not parsed:
        await message.answer(t("profile.preferences_schedule_invalid", lang))
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(user_id, vacancy_schedule_time=parsed)

    confirmation = await message.answer(t("profile.preferences_schedule_saved", lang).format(time=parsed))
    await _cleanup_schedule_messages(message, confirmation, state)
    await _refresh_preferences_message(message, user_id, state)
    await state.clear()


async def _cleanup_schedule_messages(message: types.Message, confirmation: types.Message, state: FSMContext):
    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    to_delete = [prompt_id, message.message_id, confirmation.message_id]
    for msg_id in to_delete:
        if not msg_id:
            continue
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
        except Exception as e:
            logger.debug(f"Failed to delete schedule message {msg_id}: {e}")


async def _refresh_preferences_message(message: types.Message, tg_id: str, state: FSMContext):
    data = await state.get_data()
    prefs_message_id = data.get("prefs_message_id")
    prefs_chat_id = data.get("prefs_chat_id")
    if not prefs_message_id or not prefs_chat_id:
        return

    user, lang, text, markup = await _prepare_preferences_view(
        tg_id, message.from_user.language_code if message.from_user else None
    )
    if not user or not text or not markup:
        return

    try:
        await message.bot.edit_message_text(
            chat_id=prefs_chat_id,
            message_id=prefs_message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except Exception as e:
        logger.debug(f"Failed to refresh preferences message for user {tg_id}: {e}")
