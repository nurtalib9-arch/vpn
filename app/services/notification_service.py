from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from app.core.database import async_session
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    async def notify_expiring_subscriptions(self):
        async with async_session() as session:
            now = datetime.now(timezone.utc)

            for days in [7, 3, 1]:
                target_date = now + timedelta(days=days)

                result = await session.execute(
                    select(Subscription, User)
                    .join(User)
                    .where(
                        and_(
                            Subscription.status == SubscriptionStatus.ACTIVE,
                            Subscription.end_date <= target_date,
                            Subscription.end_date > target_date - timedelta(days=1),
                        )
                    )
                )

                for sub, user in result:
                    await self._send_expiry_notification(user.telegram_id, days, sub)

    async def notify_expired_users(self):
        async with async_session() as session:
            now = datetime.now(timezone.utc)

            result = await session.execute(
                select(Subscription, User)
                .join(User)
                .where(
                    and_(
                        Subscription.status == SubscriptionStatus.EXPIRED,
                        Subscription.end_date <= now,
                        Subscription.end_date > now - timedelta(days=1),
                    )
                )
            )

            for sub, user in result:
                await self._send_expired_notification(user.telegram_id)

    async def _send_expiry_notification(self, telegram_id: int, days: int, subscription):
        from aiogram import Bot
        from app.core.config import settings

        messages = {
            7: (
                "⚠️ <b>Подписка заканчивается через 7 дней!</b>\n\n"
                f"Дата окончания: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                "Продлите сейчас, чтобы не потерять доступ к VPN."
            ),
            3: (
                "⏳ <b>Осталось 3 дня до окончания подписки!</b>\n\n"
                f"Дата окончания: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                "Не забудьте продлить подписку."
            ),
            1: (
                "🚨 <b>Завтра отключение!</b>\n\n"
                f"Дата окончания: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                "Срочно продлите подписку, чтобы не потерять доступ."
            ),
        }

        bot = Bot(token=settings.BOT_TOKEN)
        try:
            await bot.send_message(
                telegram_id,
                messages.get(days, "Подписка скоро закончится!"),
                parse_mode="HTML",
            )
        except Exception:
            logger.error(f"Failed to send expiry notification to {telegram_id}", exc_info=True)
        finally:
            await bot.session.close()

    async def _send_expired_notification(self, telegram_id: int):
        from aiogram import Bot
        from app.core.config import settings

        bot = Bot(token=settings.BOT_TOKEN)
        try:
            await bot.send_message(
                telegram_id,
                (
                    "❌ <b>Подписка истекла!</b>\n\n"
                    "Ваш доступ к VPN был отключён.\n\n"
                    "Нажмите <b>«Купить подписку»</b>, чтобы восстановить доступ."
                ),
                parse_mode="HTML",
            )
        except Exception:
            logger.error(f"Failed to notify expired user {telegram_id}", exc_info=True)
        finally:
            await bot.session.close()

    async def send_admin_message(self, text: str):
        """Send notification to all admins."""
        from aiogram import Bot
        from app.core.config import settings

        bot = Bot(token=settings.BOT_TOKEN)
        try:
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, text, parse_mode="HTML")
                except Exception:
                    logger.error(f"Failed to notify admin {admin_id}", exc_info=True)
        finally:
            await bot.session.close()
