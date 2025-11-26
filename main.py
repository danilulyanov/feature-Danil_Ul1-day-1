import asyncio
import os

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.db.database import close_database, init_database
from bot.handlers import register_all_handlers
from bot.services.hh_service import hh_service
from bot.services.openai_service import openai_service
from bot.utils.logging import get_logger
from bot.utils.scheduler import cleanup_scheduler, setup_scheduler

logger = get_logger(__name__)


async def on_startup(bot: Bot):
    os.makedirs("logs", exist_ok=True)
    logger.info("Starting HH Bot...")

    # Database
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"DB init failed: {e}")

    # HH API client
    try:
        await hh_service.init_session()
        logger.info("HH service ready")
    except Exception as e:
        logger.error(f"HH service init failed: {e}")

    # OpenAI client
    try:
        await openai_service.init_service()
        logger.info("OpenAI service ready")
    except Exception as e:
        logger.error(f"OpenAI init failed: {e}")

    # Scheduler
    try:
        await setup_scheduler(bot)
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler init failed: {e}")


async def on_shutdown(bot: Bot):
    logger.info("Shutting down bot...")

    try:
        await cleanup_scheduler()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")

    try:
        await hh_service.close_session()
        logger.info("HH client closed")
    except Exception as e:
        logger.error(f"Error closing hh: {e}")

    try:
        await close_database()
        logger.info("DB closed")
    except Exception as e:
        logger.error(f"Error closing DB: {e}")


async def main():
    bot = Bot(token=settings.TG_BOT_API_KEY)
    dp = Dispatcher()

    register_all_handlers(dp)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
