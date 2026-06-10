import asyncio
import logging
from app.services.scheduler_service import SchedulerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    scheduler = SchedulerService()
    scheduler.start()
    logger.info("Scheduler service started. Jobs: check_expiring, deactivate_expired, notify_expired")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop()
        logger.info("Scheduler service stopped")


if __name__ == "__main__":
    asyncio.run(main())
