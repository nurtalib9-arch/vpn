from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload
from app.core.database import async_session
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.tariff import Tariff
from app.models.server import Server
from app.services.marzban_service import MarzbanService
import logging

logger = logging.getLogger(__name__)


class SubscriptionService:
    async def create_subscription(
        self, user_id: int, tariff_id: int, server_id: int = None
    ) -> Subscription | None:
        async with async_session() as session:
            tariff = await session.get(Tariff, tariff_id)
            if not tariff or not tariff.is_active:
                logger.warning(f"Tariff {tariff_id} not found or inactive")
                return None

            if not server_id:
                server = await self._get_available_server(session)
                if not server:
                    logger.error("No available servers found")
                    return None
                server_id = server.id

            start_date = datetime.now(timezone.utc)
            end_date = start_date + timedelta(days=tariff.duration_months * 30)

            subscription = Subscription(
                user_id=user_id,
                tariff_id=tariff_id,
                server_id=server_id,
                start_date=start_date,
                end_date=end_date,
                status=SubscriptionStatus.PENDING,
            )
            session.add(subscription)
            await session.commit()
            await session.refresh(subscription)

            # БАГ 3: FOR UPDATE — блокировка строки для безопасного обновления счётчика
            await session.execute(
                update(Server)
                .where(Server.id == server_id)
                .with_for_update()
                .values(current_users=Server.current_users + 1)
            )
            await session.commit()

            return subscription

    async def activate_subscription(
        self, subscription_id: int, marzban_username: str
    ) -> Subscription | None:
        async with async_session() as session:
            result = await session.execute(
                update(Subscription)
                .where(Subscription.id == subscription_id)
                .values(
                    status=SubscriptionStatus.ACTIVE,
                    marzban_username=marzban_username,
                )
                .returning(Subscription)
            )
            await session.commit()
            return result.scalar_one_or_none()

    async def get_active_subscription(self, user_id: int) -> Subscription | None:
        async with async_session() as session:
            result = await session.execute(
                select(Subscription)
                # БАГ 6: eager load — не будет N+1 при обращении к .tariff/.server
                .options(
                    selectinload(Subscription.tariff),
                    selectinload(Subscription.server),
                )
                .where(
                    and_(
                        Subscription.user_id == user_id,
                        Subscription.status == SubscriptionStatus.ACTIVE,
                    )
                )
                .order_by(Subscription.end_date.desc())
            )
            return result.scalar_one_or_none()

    async def get_all_subscriptions(self, user_id: int) -> list[Subscription]:
        async with async_session() as session:
            result = await session.execute(
                select(Subscription)
                .options(
                    selectinload(Subscription.tariff),
                    selectinload(Subscription.server),
                )
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
            )
            return result.scalars().all()

    async def get_expiring_subscriptions(self, days: int) -> list[Subscription]:
        async with async_session() as session:
            target_date = datetime.now(timezone.utc) + timedelta(days=days)
            result = await session.execute(
                select(Subscription)
                .options(
                    selectinload(Subscription.user),
                    selectinload(Subscription.tariff),
                )
                .where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE,
                        Subscription.end_date <= target_date,
                        Subscription.end_date > datetime.now(timezone.utc),
                    )
                )
            )
            return result.scalars().all()

    async def deactivate_expired_subscriptions(self) -> int:
        async with async_session() as session:
            result = await session.execute(
                select(Subscription)
                .where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE,
                        Subscription.end_date <= datetime.now(timezone.utc),
                    )
                )
            )
            expired = result.scalars().all()

            marzban = MarzbanService()
            for sub in expired:
                sub.status = SubscriptionStatus.EXPIRED
                if sub.marzban_username:
                    try:
                        await marzban.disable_user(sub.marzban_username)
                    except Exception:
                        logger.error(
                            f"Failed to disable Marzban user {sub.marzban_username}",
                            exc_info=True,
                        )

                # БАГ 4: уменьшить счётчик сервера при деактивации
                await session.execute(
                    update(Server)
                    .where(Server.id == sub.server_id)
                    .with_for_update()
                    .values(current_users=Server.current_users - 1)
                )

            await session.commit()
            logger.info(f"Deactivated {len(expired)} expired subscriptions")
            return len(expired)

    async def extend_subscription(self, subscription_id: int, days: int) -> bool:
        """Extend subscription by given number of days (for referral bonuses)."""
        async with async_session() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            sub = result.scalar_one_or_none()
            if not sub:
                return False
            sub.end_date = sub.end_date + timedelta(days=days)
            await session.commit()
            return True

    async def _get_available_server(self, session) -> Server | None:
        result = await session.execute(
            select(Server)
            .where(
                and_(
                    Server.is_active == True,  # noqa
                    Server.current_users < Server.max_users,
                )
            )
            .order_by(Server.current_users.asc())
        )
        return result.scalar_one_or_none()