import asyncio
import logging
from app.core.config import validate_settings
from app.core.telegram_bot import close_bot
from app.core.marzban import close_marzban
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
    try:
        # БАГ 12: валидировать конфиг перед стартом
        validate_settings()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise

    scheduler = SchedulerService()
    
    try:
        scheduler.start()
        logger.info("Scheduler service started. Jobs: check_expiring, deactivate_expired, notify_expired")

        # БАГ 12: graceful shutdown с обработкой исключений
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Scheduler error: {e}", exc_info=True)
        raise
    finally:
        scheduler.stop()
        await close_bot()
        await close_marzban()
        logger.info("Scheduler service stopped")


if __name__ == "__main__":
    asyncio.run(main())