from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from app.services.user_service import UserService
import logging

logger = logging.getLogger(__name__)


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, (Message, CallbackQuery)):
            user_service = UserService()
            user = await user_service.get_user_by_telegram_id(event.from_user.id)

            if user and user.is_banned:
                if isinstance(event, Message):
                    await event.answer("⛔ Ваш аккаунт заблокирован.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⛔ Ваш аккаунт заблокирован.", show_alert=True)
                return None

        return await handler(event, data)
