from aiogram import Bot
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_bot_instance: Bot | None = None


async def get_bot() -> Bot:
    """Get or create singleton Telegram Bot instance."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = Bot(token=settings.BOT_TOKEN)
        logger.info("Created singleton Telegram Bot instance")
    return _bot_instance


async def close_bot():
    """Close singleton Telegram Bot instance."""
    global _bot_instance
    if _bot_instance:
        await _bot_instance.session.close()
        _bot_instance = None
        logger.info("Closed singleton Telegram Bot instance")
