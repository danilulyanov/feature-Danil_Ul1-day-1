from aiogram import Router
from aiogram.types import CallbackQuery

from bot.db import CVRepository, CVType, UserRepository
from bot.db.database import get_db_session
from bot.handlers.search.common import format_document_header, safe_answer
from bot.handlers.search.vacancy.prompts import DOCUMENT_META
from bot.services.openai_service import openai_service
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.search import get_vacancies_from_db
from bot.utils.vacancy_docs import sanitize_cover_letter_text

router = Router()
logger = get_logger(__name__)


async def _parse_callback(callback: CallbackQuery, lang: str) -> tuple[CVType, dict, str, int, str] | None:
    doc_key = "cv"
    doc_type = CVType.CV
    doc_meta = DOCUMENT_META[CVType.CV]
    try:
        if callback.data.startswith("vacancy_doc:"):
            parts = callback.data.split(":", 4)
            if len(parts) != 5:
                await safe_answer(callback, text=t("search.vacancy_detail.invalid_request", lang), show_alert=True)
                return None
            doc_key, query, idx, action = parts[1], parts[2], int(parts[3]), parts[4]
        else:
            parts = callback.data.split(":", 3)
            if len(parts) != 4:
                await safe_answer(callback, text=t("search.vacancy_detail.invalid_request", lang), show_alert=True)
                return None
            query, idx, action = parts[1], int(parts[2]), parts[3]

        doc_type = CVType.COVER_LETTER if doc_key == "cover" else CVType.CV
        doc_meta = DOCUMENT_META.get(doc_type, DOCUMENT_META[CVType.CV])
        return doc_type, doc_meta, query, idx, action
    except ValueError:
        await safe_answer(callback, text=t("search.vacancy_detail.invalid_request", lang), show_alert=True)
        return None


async def _get_user_and_lang(callback: CallbackQuery, lang: str) -> tuple[int | None, object | None, str]:
    db_session = await get_db_session()
    user_db_id = None
    user_obj = None
    if db_session:
        try:
            user_repo = UserRepository(db_session)
            user_obj = await user_repo.get_or_create_user(
                tg_user_id=str(callback.from_user.id),
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                language_code=callback.from_user.language_code,
            )
            lang = detect_lang(user_obj.language_code)
            user_db_id = user_obj.id
        except Exception as e:
            logger.error(f"Failed to get user {callback.from_user.id} from database: {e}")
        finally:
            await db_session.close()
    return user_db_id, user_obj, lang


async def _get_vacancy(user_db_id: int, query: str, idx: int, lang: str, callback: CallbackQuery) -> dict | None:
    vacancies, _ = await get_vacancies_from_db(user_db_id, query)
    if not vacancies or idx < 0 or idx >= len(vacancies):
        await safe_answer(callback, text=t("search.vacancy_detail.not_found", lang), show_alert=True)
        return None
    vacancy = vacancies[idx]
    vacancy_db_id = vacancy.get("db_id")
    if not vacancy_db_id:
        await safe_answer(callback, text=t("search.vacancy_detail.data_incomplete", lang), show_alert=True)
        return None
    return vacancy


async def _get_existing_doc(
    user_db_id: int, vacancy_db_id: int, doc_type: CVType
) -> tuple[CVRepository | None, object | None]:
    db_session = await get_db_session()
    if not db_session:
        return None, None
    cv_repo = CVRepository(db_session)
    try:
        existing_doc = await cv_repo.get_cv(user_db_id, vacancy_db_id, doc_type)
        return cv_repo, existing_doc
    except Exception as e:
        logger.error(f"Failed to fetch cached doc type={int(doc_type)} for user {user_db_id}: {e}")
        return cv_repo, None


@router.callback_query(lambda c: c.data.startswith("vacancy_cv:") or c.data.startswith("vacancy_doc:"))
async def vacancy_cv_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    await safe_answer(callback)
    lang = detect_lang(callback.from_user.language_code if callback.from_user else None)

    db_session = None
    try:
        parsed = await _parse_callback(callback, lang)
        if not parsed:
            return
        doc_type, doc_meta, query, idx, action = parsed

        user_db_id, user_obj, lang = await _get_user_and_lang(callback, lang)
        if not user_db_id:
            await safe_answer(callback, text=t("search.vacancy_detail.user_not_found", lang), show_alert=True)
            return

        vacancy = await _get_vacancy(user_db_id, query, idx, lang, callback)
        if not vacancy:
            return
        vacancy_db_id = vacancy["db_id"]

        cv_repo, existing_doc = await _get_existing_doc(user_db_id, vacancy_db_id, doc_type)

        if action in {"send", "generate"} and existing_doc and action != "regen":
            header, _ = format_document_header(vacancy, lang, doc_type)
            await callback.message.answer(
                f"{header}\n\n{existing_doc.text}",
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
            return

        if action == "send" and not existing_doc:
            await safe_answer(callback, text=t(doc_meta["no_cache_key"], lang), show_alert=True)
            return

        prefs = user_obj.preferences if user_obj and user_obj.preferences else {}
        user_resume = prefs.get("resume")
        user_skills = prefs.get("skills")
        llm_settings = prefs.get("llm_settings") or {}
        user_prompt = None

        if not openai_service._initialized and not (llm_settings.get("api_key")):
            await safe_answer(callback, text=t("search.vacancy_detail.llm_unavailable", lang), show_alert=True)
            return

        messages = doc_meta["prompt_builder"](vacancy, user_resume, user_skills, user_prompt, lang)
        generating_msg = await callback.message.answer(t(doc_meta["generating_key"], lang))
        doc_text = await openai_service.chat_completion(
            messages,
            model=openai_service.settings.LLM_MODEL,
            max_tokens=doc_meta["max_tokens"],
            llm_overrides=llm_settings or None,
        )

        if not doc_text or not str(doc_text).strip():
            logger.error(
                "LLM returned empty document",
                extra={
                    "user_id": user_id,
                    "vacancy_id": vacancy_db_id,
                    "query": query,
                    "llm_model": openai_service.settings.LLM_MODEL,
                    "doc_type": int(doc_type),
                },
            )
            await callback.message.answer(t(doc_meta["empty_key"], lang))
            return

        if cv_repo:
            try:
                normalized_text = str(doc_text)
                if doc_type == CVType.COVER_LETTER:
                    normalized_text = sanitize_cover_letter_text(normalized_text)
                await cv_repo.upsert_cv(user_db_id, vacancy_db_id, normalized_text, doc_type)
                doc_text = normalized_text
            except Exception as e:
                logger.error(f"Failed to cache doc type={int(doc_type)} for user {user_db_id}: {e}")

        header, _ = format_document_header(vacancy, lang, doc_type)
        try:
            await generating_msg.edit_text(
                f"{header}\n\n{doc_text}",
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
        except Exception:
            await callback.message.answer(
                f"{header}\n\n{doc_text}",
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
    except ValueError:
        await safe_answer(callback, text=t("search.vacancy_detail.invalid_request", lang), show_alert=True)
    except Exception as e:
        logger.error(f"Failed to handle document generation for user {user_id}: {e}")
        try:
            await callback.message.answer(t(doc_meta["failed_key"], lang))
        except Exception:
            await safe_answer(callback, text=t(doc_meta["failed_key"], lang), show_alert=True)
    finally:
        try:
            if db_session:
                await db_session.close()
        except Exception as close_err:
            logger.warning(f"Failed to close DB session after CV handler: {close_err}")
