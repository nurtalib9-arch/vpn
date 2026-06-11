import asyncio
import logging
import signal
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from app.core.config import settings, validate_settings
from app.core.redis import redis_client
from app.core.telegram_bot import get_bot, close_bot
from app.core.marzban import close_marzban
from app.bot.handlers import start, payments, profile, referral, gift
from app.bot.middlewares.logging_middleware import LoggingMiddleware
from app.bot.middlewares.ban_middleware import BanMiddleware

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    logger.info("Starting VPN bot...")
    if settings.WEBHOOK_URL:
        await bot.set_webhook(
            url=settings.WEBHOOK_URL,
            drop_pending_updates=True,
        )
        logger.info(f"Webhook set: {settings.WEBHOOK_URL}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Running in polling mode")


async def on_shutdown(bot: Bot):
    logger.info("Shutting down...")
    # БАГ 13: закрываем singleton сервисы правильно
    await close_bot()
    await close_marzban()
    await bot.session.close()


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    storage = RedisStorage(redis=redis_client)

    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=storage)

    # Middleware
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(BanMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.callback_query.middleware(BanMiddleware())

    # Routers
    dp.include_router(start.router)
    dp.include_router(payments.router)
    dp.include_router(profile.router)
    dp.include_router(referral.router)
    dp.include_router(gift.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return bot, dp


async def run_polling():
    bot, dp = create_bot_and_dispatcher()
    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def run_webhook():
    bot, dp = create_bot_and_dispatcher()
    app = web.Application()

    webhook_path = "/webhook/telegram"
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8001)
    await site.start()

    logger.info(f"Webhook server running on port 8001, path: {webhook_path}")
    await asyncio.Event().wait()


async def main():
    # БАГ 9: валидировать конфиг на старте
    try:
        validate_settings()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    
    if settings.WEBHOOK_URL:
        await run_webhook()
    else:
        await run_polling()


if __name__ == "__main__":
    asyncio.run(main())