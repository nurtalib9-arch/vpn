import secrets
import string
import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.database import async_session
from app.models.user import User
from app.models.referral import Referral

logger = logging.getLogger(__name__)


class UserService:
    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
        referral_code: str = None,
    ) -> User:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user:
                if not user.is_banned:
                    user.username = username
                    user.first_name = first_name
                    user.last_name = last_name
                    await session.commit()
                return user

            new_referral_code = self._generate_referral_code()

            referrer_id = None
            if referral_code:
                referrer_result = await session.execute(
                    select(User).where(User.referral_code == referral_code)
                )
                referrer = referrer_result.scalar_one_or_none()
                if referrer and referrer.telegram_id != telegram_id:
                    referrer_id = referrer.id

            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                referral_code=new_referral_code,
                referred_by=referrer_id,
            )
            session.add(user)

            try:
                await session.commit()
                await session.refresh(user)

                if referrer_id:
                    await self._process_referral_bonus(session, referrer_id, user.id)

            except IntegrityError:
                logger.error("IntegrityError creating user, rolling back", exc_info=True)
                await session.rollback()
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                return result.scalar_one()

            return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    async def get_user_by_referral_code(self, referral_code: str) -> User | None:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.referral_code == referral_code)
            )
            return result.scalar_one_or_none()

    async def ban_user(self, telegram_id: int) -> bool:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return False
            user.is_banned = True
            await session.commit()
            return True

    async def unban_user(self, telegram_id: int) -> bool:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return False
            user.is_banned = False
            await session.commit()
            return True

    def _generate_referral_code(self) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(8))

    async def _process_referral_bonus(self, session, referrer_id: int, referred_id: int):
        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            bonus_days_given=3,
        )
        session.add(referral)
        await session.commit()
