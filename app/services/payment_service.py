from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select, update
from app.core.database import async_session
from app.models.payment import Payment
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.subscription_service import SubscriptionService
from app.services.marzban_service import MarzbanService
import logging
import json
import uuid

logger = logging.getLogger(__name__)

# Referral bonus days per tariff duration (months)
REFERRAL_BONUS_DAYS = {1: 10, 3: 25, 6: 45, 12: 65}


class PaymentService:
    async def create_payment(
        self, user_id: int, amount: Decimal, provider: str, tariff_id: int
    ) -> Payment:
        async with async_session() as session:
            payment = Payment(
                user_id=user_id,
                amount=amount,
                provider=provider,
                provider_payment_id=str(uuid.uuid4()),
                status="pending",
                metadata_json=json.dumps({"tariff_id": tariff_id}),
            )
            session.add(payment)
            await session.commit()
            await session.refresh(payment)
            return payment

    async def get_payment_by_provider_id(self, provider_payment_id: str) -> Payment | None:
        async with async_session() as session:
            result = await session.execute(
                select(Payment).where(Payment.provider_payment_id == provider_payment_id)
            )
            return result.scalar_one_or_none()

    async def process_successful_payment(self, provider_payment_id: str) -> Payment | None:
        async with async_session() as session:
            # Баг 3: FOR UPDATE — блокировка строки, исключает race condition
            # при одновременном получении дублирующих webhook'ов
            result = await session.execute(
                select(Payment)
                .where(Payment.provider_payment_id == provider_payment_id)
                .with_for_update()
            )
            payment = result.scalar_one_or_none()

            if not payment:
                logger.warning(f"Payment not found: {provider_payment_id}")
                return None

            if payment.status == "success":
                logger.info(f"Payment {provider_payment_id} already processed, skipping")
                return payment  # идемпотентно — возвращаем, не None

            metadata = json.loads(payment.metadata_json or "{}")
            tariff_id = metadata.get("tariff_id")
            gift_recipient_id = metadata.get("gift_recipient_id")

            if not tariff_id:
                logger.error(f"No tariff_id in metadata for payment {provider_payment_id}")
                payment.status = "failed"
                await session.commit()
                return None

            # Для подарка — подписка идёт получателю, оплату делает отправитель
            target_user_id = gift_recipient_id if gift_recipient_id else payment.user_id

            subscription_service = SubscriptionService()
            subscription = await subscription_service.create_subscription(
                target_user_id, tariff_id
            )

            if not subscription:
                logger.error(
                    f"Failed to create subscription for payment {provider_payment_id}, "
                    f"tariff_id={tariff_id}, user_id={target_user_id}"
                )
                payment.status = "failed"
                await session.commit()
                return None

            user = await session.get(User, payment.user_id)
            if not user:
                logger.error(f"User {payment.user_id} not found for payment {provider_payment_id}")
                payment.status = "failed"
                await session.commit()
                return None

            # БАГ 16: проверить, что tariff загружен
            if not subscription.tariff:
                logger.error(
                    f"Tariff {tariff_id} not loaded for subscription {subscription.id}"
                )
                payment.status = "failed"
                await session.commit()
                return None

            marzban_username = f"user_{user.telegram_id}_{subscription.id}"
            expire_days = subscription.tariff.duration_months * 30

            # Баг 7: детальное логирование перед вызовом Marzban
            logger.info(
                f"Creating Marzban user: username={marzban_username}, "
                f"expire_days={expire_days}, tariff_id={tariff_id}"
            )

            try:
                marzban = MarzbanService()
                await marzban.create_user(marzban_username, expire_days)
            except Exception:
                logger.error(
                    f"Marzban API failed for payment {provider_payment_id}: "
                    f"username={marzban_username}, expire_days={expire_days}",
                    exc_info=True,
                )
                # Баг 5: удаляем зависшую подписку и помечаем платёж failed
                # чтобы не было PENDING-записей без VPN-ключа
                await session.delete(subscription)
                payment.status = "failed"
                await session.commit()
                logger.warning(
                    f"Subscription {subscription.id} deleted, payment {provider_payment_id} marked failed"
                )
                return None

            # Marzban успешен — фиксируем всё атомарно
            payment.status = "success"
            payment.paid_at = datetime.now(timezone.utc)
            payment.subscription_id = subscription.id

            await session.execute(
                update(Subscription)
                .where(Subscription.id == subscription.id)
                .values(
                    status=SubscriptionStatus.ACTIVE,
                    marzban_username=marzban_username,
                )
            )

            await session.commit()
            logger.info(
                f"Payment {provider_payment_id} processed OK: "
                f"subscription_id={subscription.id}, marzban={marzban_username}"
            )

            # Реферальный бонус — вне основной транзакции (не критично)
            await self._process_referral_purchase_bonus(
                payment.user_id, subscription.tariff.duration_months
            )

            return payment

    async def _process_referral_purchase_bonus(self, user_id: int, tariff_months: int):
        """Бонусные дни рефереру при покупке приглашённого пользователя."""
        from app.models.referral import Referral

        bonus_days = REFERRAL_BONUS_DAYS.get(tariff_months, 0)
        if not bonus_days:
            return

        try:
            async with async_session() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if not user or not user.referred_by:
                    return

                subscription_service = SubscriptionService()
                referrer_sub = await subscription_service.get_active_subscription(user.referred_by)
                if referrer_sub:
                    await subscription_service.extend_subscription(referrer_sub.id, bonus_days)
                    logger.info(
                        f"Referrer {user.referred_by} extended by {bonus_days} days "
                        f"(referred user {user_id} purchased {tariff_months}mo)"
                    )

                ref_result = await session.execute(
                    select(Referral).where(
                        Referral.referrer_id == user.referred_by,
                        Referral.referred_id == user_id,
                    )
                )
                referral = ref_result.scalar_one_or_none()
                if referral:
                    referral.bonus_days_given += bonus_days
                    await session.commit()
        except Exception:
            # Реферальный бонус не критичен — логируем и продолжаем
            logger.error(
                f"Failed to process referral bonus for user {user_id}", exc_info=True
            )
