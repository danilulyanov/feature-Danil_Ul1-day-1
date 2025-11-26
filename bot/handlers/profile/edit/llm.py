import html

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.keyboards import llm_keyboard
from bot.handlers.profile.states import EditProfile
from bot.utils.i18n import detect_lang, t
from bot.utils.lang import resolve_lang
from bot.utils.logging import get_logger
from bot.utils.profile_helpers import hide_key

logger = get_logger(__name__)
router = Router()


async def send_llm_menu(message_obj: types.Message | types.CallbackQuery, tg_id: str, edit: bool = False):
    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(
        user.language_code
        if user and user.language_code
        else (message_obj.from_user.language_code if message_obj.from_user else None)
    )
    target = message_obj.message if isinstance(message_obj, types.CallbackQuery) else message_obj

    if not user:
        await target.answer(t("profile.no_profile", lang))
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()
        return

    prefs = user.preferences or {}
    llm = prefs.get("llm_settings") or {}
    markup = llm_keyboard(lang)

    if llm:
        text = t(
            "profile.llm_menu",
            lang,
            model=html.escape(llm.get("model") or t("profile.not_set", lang)),
            base_url=html.escape(llm.get("base_url") or t("profile.not_set", lang)),
            api_key=hide_key(llm.get("api_key")),
        )
    else:
        text = t("profile.llm_menu_empty", lang)

    if isinstance(message_obj, types.CallbackQuery) and edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await message_obj.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()


@router.callback_query(F.data == "llm_menu")
async def cb_llm_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_llm_menu(call, str(call.from_user.id), edit=True)


@router.callback_query(F.data.in_({"llm_edit", "edit_llm"}))
async def cb_edit_llm(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    await call.message.answer(t("profile.edit_llm_prompt", lang), parse_mode="HTML")
    await state.set_state(EditProfile.llm)
    await call.answer()


@router.callback_query(F.data == "llm_back_profile")
async def cb_llm_back_profile(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    from bot.handlers.profile.view import send_profile_view

    await send_profile_view(str(call.from_user.id), call.message)
    await call.answer()


@router.message(EditProfile.llm)
async def save_llm(message: types.Message, state: FSMContext):
    llm_raw = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if not llm_raw:
        await message.answer(t("profile.edit_llm_empty", lang))
        return

    if llm_raw.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_preferences(user_id, llm_settings=None)
        await message.answer(t("profile.edit_llm_cleared", lang))
        await send_llm_menu(message, user_id)
        await state.clear()
        return

    try:
        model, url, key = (s.strip() for s in llm_raw.split(";"))
    except ValueError:
        await message.answer(t("profile.edit_llm_bad_format", lang), parse_mode="HTML")
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(user_id, llm_settings={"model": model, "base_url": url, "api_key": key})

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete message with LLM settings for user {user_id}: {e}")

    await message.answer(t("profile.edit_llm_updated", lang))
    await send_llm_menu(message, user_id)
    await state.clear()
