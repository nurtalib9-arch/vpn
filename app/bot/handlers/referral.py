from aiogram import Router, F
from aiogram.types import Message
from app.services.user_service import UserService
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "👥 Реферальная система")
async def show_referral(message: Message):
    user_service = UserService()
    user = await user_service.get_user_by_telegram_id(message.from_user.id)

    if not user:
        return

    bot_info = await message.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"

    referrals_count = len(user.referrals_made)
    bonus_days = sum(r.bonus_days_given for r in user.referrals_made)

    await message.answer(
        f"👥 <b>Реферальная система</b>\n\n"
        f"Ваша ссылка:\n<code>{referral_link}</code>\n\n"
        f"<b>Бонусы за регистрацию:</b>\n"
        f"• Друг получает <b>+3 дня</b> бесплатно\n"
        f"• Вы получаете <b>+1 день</b> за каждого друга\n\n"
        f"<b>Бонусы за покупку друга:</b>\n"
        f"• 1 мес → <b>+10 дней</b>\n"
        f"• 3 мес → <b>+25 дней</b>\n"
        f"• 6 мес → <b>+45 дней</b>\n"
        f"• 12 мес → <b>+65 дней</b>\n\n"
        f"👥 Приглашено: <b>{referrals_count} чел.</b>\n"
        f"🎁 Получено бонусных дней: <b>{bonus_days}</b>",
        parse_mode="HTML",
    )
