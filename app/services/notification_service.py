from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from app.core.database import async_session
from app.core.telegram_bot import get_bot
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
import logging

logger = logging.getLogger(__name__)

# Track last notification times to prevent spam (in-memory cache)
_last_notifications: dict[int, dict[int, datetime]] = {}  # {user_id: {days: timestamp}}


class NotificationService:
    async def notify_expiring_subscriptions(self):
        """
        БАГ 7: Отправлять уведомления только один раз в день для каждого дня.
        Проверяем, когда было последнее уведомление для пользователя.
        """
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
                    # Проверить, не отправляли ли уже уведомление на этот день
                    if not self._should_send_notification(user.id, days):
                        logger.debug(
                            f"Skipping notification for user {user.id} "
                            f"(already sent for {days} days)"
                        )
                        continue

                    await self._send_expiry_notification(user.telegram_id, days, sub)
                    self._mark_notification_sent(user.id, days)

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
                # Отправить только один раз в день
                if not self._should_send_notification(user.id, 0):  # 0 = expired
                    continue

                await self._send_expired_notification(user.telegram_id)
                self._mark_notification_sent(user.id, 0)

    async def _send_expiry_notification(self, telegram_id: int, days: int, subscription):
        """БАГ 1: Использовать singleton Bot."""
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

        try:
            bot = await get_bot()
            await bot.send_message(
                telegram_id,
                messages.get(days, "Подписка скоро закончится!"),
                parse_mode="HTML",
            )
            logger.info(
                f"Sent {days}-day expiry notification to user {telegram_id}"
            )
        except Exception:
            logger.error(
                f"Failed to send expiry notification to {telegram_id}",
                exc_info=True,
            )

    async def _send_expired_notification(self, telegram_id: int):
        """БАГ 1: Использовать singleton Bot."""
        try:
            bot = await get_bot()
            await bot.send_message(
                telegram_id,
                (
                    "❌ <b>Подписка истекла!</b>\n\n"
                    "Ваш доступ к VPN был отключён.\n\n"
                    "Нажмите <b>«Купить подписку»</b>, чтобы восстановить доступ."
                ),
                parse_mode="HTML",
            )
            logger.info(f"Sent expired notification to user {telegram_id}")
        except Exception:
            logger.error(
                f"Failed to notify expired user {telegram_id}",
                exc_info=True,
            )

    async def send_admin_message(self, text: str):
        """Send notification to all admins."""
        from app.core.config import settings

        try:
            bot = await get_bot()
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, text, parse_mode="HTML")
                except Exception:
                    logger.error(f"Failed to notify admin {admin_id}", exc_info=True)
        except Exception:
            logger.error("Failed to send admin message", exc_info=True)

    def _should_send_notification(self, user_id: int, days: int) -> bool:
        """Check if we should send notification (max once per day)."""
        now = datetime.now(timezone.utc)

        if user_id not in _last_notifications:
            return True

        last_sent = _last_notifications[user_id].get(days)
        if last_sent is None:
            return True

        # Send again only if 24 hours passed
        return (now - last_sent).total_seconds() > 86400

    def _mark_notification_sent(self, user_id: int, days: int):
        """Mark notification as sent for this user and day."""
        if user_id not in _last_notifications:
            _last_notifications[user_id] = {}

        _last_notifications[user_id][days] = datetime.now(timezone.utc)