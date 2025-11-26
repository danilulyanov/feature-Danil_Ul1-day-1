import html

from aiogram import Router, types
from aiogram.filters import Command

from bot.db.database import get_db_session
from bot.db.search_query_repository import SearchQueryRepository
from bot.db.user_repository import UserRepository
from bot.handlers.profile.keyboards import profile_keyboard
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.profile_helpers import build_skills_preview, format_search_filters, short

logger = get_logger(__name__)
router = Router()


async def send_profile_view(tg_id: str, message_obj: types.Message):
    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(
        user.language_code if user else (message_obj.from_user.language_code if message_obj.from_user else None)
    )

    if not user:
        await message_obj.answer(t("profile.no_profile", lang))
        return

    prefs = user.preferences or {}
    search_filters = prefs.get("search_filters", {})

    city = html.escape(user.city) if user.city else "not set"
    desired_position = html.escape(prefs.get("desired_position", "")) if prefs.get("desired_position") else "not set"
    skills_list = prefs.get("skills", [])
    skills_count, skills_preview = build_skills_preview(skills_list)
    skills = f"{skills_count} ({html.escape(skills_preview)})" if skills_count else t("profile.not_set", lang)
    username = f"@{html.escape(user.username)}" if user.username else "not set"
    name = f"{html.escape(user.first_name or '')} {html.escape(user.last_name or '')}".strip()
    search_filters_text = format_search_filters(search_filters, lang)
    last_search = t("profile.not_set", lang)
    try:
        async with await get_db_session() as session:
            sq_repo = SearchQueryRepository(session)
            latest = await sq_repo.get_latest_search_query_any(user.id)
            if latest and latest.query_text:
                last_search = html.escape(latest.query_text)
    except Exception as e:
        logger.warning(f"Failed to load last search for user {user.id}: {e}")

    text = t(
        "profile.view",
        lang,
        tg_id=user.tg_user_id,
        username=username,
        name=name or "not set",
        city=city,
        desired_position=desired_position,
        skills=skills,
        resume=short(prefs.get("resume"), lang),
        last_search=last_search,
        search_filters=search_filters_text,
    )

    await message_obj.answer(text, parse_mode="HTML", reply_markup=profile_keyboard(lang, skills_count, skills_preview))


@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    await send_profile_view(str(message.from_user.id), message)


@router.message(Command("resume"))
async def cmd_resume(message: types.Message):
    tg_id = str(message.from_user.id)

    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(user.language_code if user else (message.from_user.language_code if message.from_user else None))

    if not user:
        await message.answer(t("profile.no_profile", lang))
        return

    prefs = user.preferences or {}
    resume = prefs.get("resume")

    if not resume:
        await message.answer(t("profile.resume_missing", lang))
        return

    await message.answer(
        f"{t('profile.resume_header', lang)}\n\n" + html.escape(resume),
        parse_mode="HTML",
    )
