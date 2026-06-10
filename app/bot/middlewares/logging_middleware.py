from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
import logging

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
            username = event.from_user.username or "N/A"

            if isinstance(event, Message) and event.text:
                logger.info(f"MSG user={user_id} @{username}: {event.text[:100]}")
            elif isinstance(event, CallbackQuery):
                logger.info(f"CBK user={user_id} @{username}: {event.data}")

        return await handler(event, data)
