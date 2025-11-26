from collections.abc import Callable
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.utils.logging import get_logger

# Create logger for this module
scheduler_logger = get_logger(__name__)


class BotScheduler:
    """Scheduler for periodic tasks with comprehensive logging"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.jobs: dict[str, Callable] = {}

    def start(self):
        """Start the scheduler with logging"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                scheduler_logger.success("Scheduler started successfully")
            else:
                scheduler_logger.warning("Scheduler was already running")
        except Exception as e:
            scheduler_logger.error(f"Failed to start scheduler: {e}")
            raise

    def shutdown(self):
        """Shutdown the scheduler with logging"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                scheduler_logger.success("Scheduler shutdown successfully")
            else:
                scheduler_logger.info("Scheduler was not running")
        except Exception as e:
            scheduler_logger.error(f"Failed to shutdown scheduler: {e}")
            raise

    def add_job(
        self,
        func: Callable,
        trigger: CronTrigger,
        job_id: str,
        job_name: str = None,
        job_args: list | tuple | None = None,
        job_kwargs: dict | None = None,
    ):
        """Add a job to the scheduler with comprehensive logging"""
        try:
            job = self.scheduler.add_job(
                func,
                trigger,
                args=job_args or [],
                kwargs=job_kwargs or {},
                id=job_id,
                name=job_name or job_id,
            )

            self.jobs[job_id] = func
            scheduler_logger.info(f"Job '{job_id}' added to scheduler: {job_name or job_id}")
            scheduler_logger.debug(f"Job '{job_id}' scheduled with trigger: {trigger}")

            return job
        except Exception as e:
            scheduler_logger.error(f"Failed to add job '{job_id}' to scheduler: {e}")
            raise

    def remove_job(self, job_id: str):
        """Remove a job from the scheduler with logging"""
        try:
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                scheduler_logger.info(f"Job '{job_id}' removed from scheduler")
            else:
                scheduler_logger.warning(f"Attempted to remove non-existent job '{job_id}'")
        except Exception as e:
            scheduler_logger.error(f"Failed to remove job '{job_id}' from scheduler: {e}")
            raise

    def list_jobs(self) -> list[dict]:
        """List all scheduled jobs with logging"""
        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                job_info = {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time,
                    "trigger": str(job.trigger),
                }
                jobs.append(job_info)

            scheduler_logger.debug(f"Listed {len(jobs)} scheduled jobs")
            return jobs
        except Exception as e:
            scheduler_logger.error(f"Failed to list scheduled jobs: {e}")
            return []


# Global scheduler instance
bot_scheduler = BotScheduler()


async def setup_scheduler(bot: Bot | None = None):
    """Setup the scheduler with logging"""
    try:
        bot_scheduler.start()
        scheduler_logger.info("Scheduler setup completed successfully")

        if bot:
            try:
                from bot.tasks.vacancy_delivery import run_daily_vacancies

                bot_scheduler.add_job(
                    run_daily_vacancies,
                    CronTrigger(minute="*"),
                    job_id="daily_vacancies",
                    job_name="Daily Vacancy Delivery",
                    job_args=[bot],
                )
                scheduler_logger.info("Daily vacancy delivery job registered")
            except Exception as e:
                scheduler_logger.error(f"Failed to register daily vacancy job: {e}")

        return True
    except Exception as e:
        scheduler_logger.error(f"Failed to setup scheduler: {e}")
        return False


async def example_task():
    """Example task for the scheduler"""
    current_time = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    scheduler_logger.info(f"Example task executed at {current_time}")


async def cleanup_scheduler():
    """Cleanup the scheduler with logging"""
    try:
        bot_scheduler.shutdown()
        scheduler_logger.info("Scheduler cleanup completed successfully")
    except Exception as e:
        scheduler_logger.error(f"Failed to cleanup scheduler: {e}")
