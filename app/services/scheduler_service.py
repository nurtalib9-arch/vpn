from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.notification_service import NotificationService
from app.services.subscription_service import SubscriptionService
import logging

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.notification_service = NotificationService()
        self.subscription_service = SubscriptionService()

    def start(self):
        # Check expiring subscriptions every 6 hours
        self.scheduler.add_job(
            self.check_expiring_subscriptions,
            CronTrigger(hour="*/6"),
            id="check_expiring",
            replace_existing=True,
        )

        # Deactivate expired subscriptions at midnight
        self.scheduler.add_job(
            self.deactivate_expired,
            CronTrigger(hour=0, minute=0),
            id="deactivate_expired",
            replace_existing=True,
        )

        # Notify expired users at 01:00
        self.scheduler.add_job(
            self.notify_expired,
            CronTrigger(hour=1, minute=0),
            id="notify_expired",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Scheduler started with 3 jobs")

    def stop(self):
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    async def check_expiring_subscriptions(self):
        try:
            await self.notification_service.notify_expiring_subscriptions()
            logger.info("Expiring subscription check completed")
        except Exception:
            logger.error("Failed to check expiring subscriptions", exc_info=True)

    async def deactivate_expired(self):
        try:
            count = await self.subscription_service.deactivate_expired_subscriptions()
            logger.info(f"Deactivated {count} expired subscriptions")
        except Exception:
            logger.error("Failed to deactivate expired subscriptions", exc_info=True)

    async def notify_expired(self):
        try:
            await self.notification_service.notify_expired_users()
            logger.info("Expired user notification completed")
        except Exception:
            logger.error("Failed to notify expired users", exc_info=True)
