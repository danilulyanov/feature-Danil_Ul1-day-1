from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot

from bot.db.database import get_db_session
from bot.db.search_query_repository import SearchQueryRepository
from bot.db.user_repository import UserRepository
from bot.handlers.search.common import VACANCIES_PER_PAGE, build_search_keyboard
from bot.services.hh_service import hh_service
from bot.utils.i18n import detect_lang
from bot.utils.logging import get_logger
from bot.utils.search import cache_vacancies, format_search_page, perform_search, store_search_results

logger = get_logger(__name__)

# Temporary default timezone until user timezones are added to preferences
DEFAULT_TZ = ZoneInfo("Europe/Moscow")
MAX_SENT_IDS = 200
MAX_VACANCIES_PER_USER = 10


def _already_sent_today(prefs: dict, now_local: datetime) -> bool:
    last_sent_raw = prefs.get("vacancy_last_sent_at")
    if not last_sent_raw:
        return False
    try:
        last_dt = datetime.fromisoformat(last_sent_raw)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)
        return last_dt.astimezone(now_local.tzinfo).date() == now_local.date()
    except Exception:
        return False


def _get_timezone(prefs: dict) -> ZoneInfo:
    tz_name = prefs.get("timezone")
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            logger.debug(f"Invalid timezone '{tz_name}', falling back to default")
    return DEFAULT_TZ


async def run_daily_vacancies(bot: Bot):
    """Send daily vacancies to users with a schedule time set."""
    if not hh_service.session:
        logger.warning("HH service not initialized; skipping daily vacancies job")
        return

    now_utc = datetime.now(UTC)
    async with await get_db_session() as session:
        user_repo = UserRepository(session)
        users = await user_repo.get_users_with_schedule()

    processed = 0
    for user in users:
        try:
            sent = await send_vacancies_to_user(user, bot, now_utc)
            if sent:
                processed += 1
        except Exception as e:
            logger.error(f"Failed to process user {user.tg_user_id} in scheduler: {e}")

    if processed:
        logger.debug(f"Daily vacancies job finished, sent to {processed} user(s)")


async def send_vacancies_to_user(user, bot: Bot, now_utc: datetime, force: bool = False, mark_sent: bool = True):
    prefs = user.preferences or {}
    user_tz = _get_timezone(prefs)
    now_local = now_utc.astimezone(user_tz)
    current_time = now_local.strftime("%H:%M")

    schedule_time = prefs.get("vacancy_schedule_time")
    if not schedule_time:
        return False

    if not force and schedule_time != current_time:
        return False

    if not force and _already_sent_today(prefs, now_local):
        return False

    sent_ids = prefs.get("sent_vacancy_ids") or []
    sent_ids_set = set(sent_ids)
    lang = detect_lang(user.language_code)

    async with await get_db_session() as session:
        search_repo = SearchQueryRepository(session)
        last_query = await search_repo.get_latest_search_query_any(user.id)

    if not last_query or not last_query.query_text:
        logger.info(f"Skip user {user.tg_user_id}: no last search query")
        return False

    filters = prefs.get("search_filters", {})
    area_id = user.hh_area_id

    try:
        results, response_time = await perform_search(
            last_query.query_text,
            per_page=MAX_VACANCIES_PER_USER,
            max_pages=1,
            search_in_name_only=True,
            area_id=area_id,
            filters=filters,
        )
    except Exception as e:
        logger.error(f"Search failed for user {user.tg_user_id}: {e}")
        return False

    if not results or not results.get("items"):
        logger.info(f"No vacancies found for user {user.tg_user_id} at {current_time}")
        return False

    vacancies_all = results.get("items", [])
    vacancies_filtered = [vac for vac in vacancies_all if force or vac.get("id") not in sent_ids_set]
    if not vacancies_filtered:
        logger.info(f"All vacancies already sent to user {user.tg_user_id}, skipping")
        return False

    vacancies = vacancies_filtered[:MAX_VACANCIES_PER_USER]
    total_found = len(vacancies)

    # Persist and cache for detail/pagination handlers
    await store_search_results(
        user.id, last_query.query_text, vacancies, response_time, per_page=MAX_VACANCIES_PER_USER
    )
    cache_vacancies(user.id, last_query.query_text, vacancies, total_found)

    page = 0
    total_pages = (len(vacancies) + VACANCIES_PER_PAGE - 1) // VACANCIES_PER_PAGE
    text = format_search_page(last_query.query_text, vacancies, page, VACANCIES_PER_PAGE, total_found, lang)
    reply_markup = build_search_keyboard(last_query.query_text, page, total_pages, VACANCIES_PER_PAGE, len(vacancies))

    try:
        await bot.send_message(
            chat_id=user.tg_user_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"Failed to send vacancies to user {user.tg_user_id}: {e}")
        return False

    if not mark_sent:
        return True

    new_ids = [vac.get("id") for vac in vacancies if vac.get("id")]
    combined_ids = (sent_ids + new_ids)[-MAX_SENT_IDS:]

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(
            user.tg_user_id,
            vacancy_last_sent_at=now_utc.isoformat(),
            sent_vacancy_ids=combined_ids,
        )

    return True
