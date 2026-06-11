from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.core.database import async_session
from app.bot.keyboards.main_menu import get_profile_menu
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.core.marzban import get_marzban
from app.utils.qr_generator import generate_qr_code
from app.models.user import User
from app.models.referral import Referral
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message):
    user_service = UserService()
    user = await user_service.get_user_by_telegram_id(message.from_user.id)

    if not user:
        await message.answer("❌ Пользователь не найден.")
        return

    subscription_service = SubscriptionService()
    active_sub = await subscription_service.get_active_subscription(user.id)

    if active_sub:
        days_left = (active_sub.end_date - datetime.now(timezone.utc)).days
        tariff_name = active_sub.tariff.name if active_sub.tariff else "—"
        server_name = active_sub.server.location if active_sub.server else "—"
        status_text = (
            f"✅ <b>Активна</b>\n"
            f"Тариф: {tariff_name}\n"
            f"Сервер: {server_name}\n"
            f"До: {active_sub.end_date.strftime('%d.%m.%Y')}\n"
            f"Осталось: <b>{days_left} дн.</b>"
        )
        has_sub = True
    else:
        status_text = "❌ <b>Нет активной подписки</b>"
        has_sub = False

    # БАГ 11: явно загружаем рефералы с ограничением
    async with async_session() as session:
        result = await session.execute(
            select(Referral)
            .where(Referral.referrer_id == user.id)
        )
        referrals = result.scalars().all()

    referrals_count = len(referrals)
    bonus_days = sum(r.bonus_days_given for r in referrals)

    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{user.telegram_id}</code>\n"
        f"Реф. код: <code>{user.referral_code}</code>\n\n"
        f"📊 <b>Подписка:</b>\n{status_text}\n\n"
        f"👥 Рефералов: {referrals_count}\n"
        f"🎁 Бонусных дней получено: {bonus_days}",
        reply_markup=get_profile_menu(has_sub),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "get_key")
async def get_vpn_key(callback: CallbackQuery):
    user_service = UserService()
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    subscription_service = SubscriptionService()
    active_sub = await subscription_service.get_active_subscription(user.id)

    if not active_sub or not active_sub.marzban_username:
        await callback.answer("❌ Нет активной подписки.", show_alert=True)
        return

    # БАГ 6: используем singleton Marzban
    marzban = await get_marzban()
    try:
        links = await marzban.get_user_links(active_sub.marzban_username)
        if links:
            links_text = "\n".join(f"<code>{link}</code>" for link in links[:3])
            await callback.message.answer(
                f"🔑 <b>Ваши ключи подключения:</b>\n\n{links_text}\n\n"
                "Скопируйте ключ и вставьте в v2rayNG или Streisand.",
                parse_mode="HTML",
            )
        else:
            sub_url = await marzban.get_user_subscription_url(active_sub.marzban_username)
            await callback.message.answer(
                f"🔑 <b>Ссылка на подписку:</b>\n\n<code>{sub_url}</code>\n\n"
                "Используйте эту ссылку в клиенте для автоматической настройки.",
                parse_mode="HTML",
            )
    except Exception:
        logger.error("Failed to get VPN key", exc_info=True)
        await callback.answer("❌ Ошибка получения ключа. Попробуйте позже.", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "get_qr")
async def get_qr_code(callback: CallbackQuery):
    user_service = UserService()
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    subscription_service = SubscriptionService()
    active_sub = await subscription_service.get_active_subscription(user.id)

    if not active_sub or not active_sub.marzban_username:
        await callback.answer("❌ Нет активной подписки.", show_alert=True)
        return

    # БАГ 6: используем singleton Marzban
    marzban = await get_marzban()
    try:
        links = await marzban.get_user_links(active_sub.marzban_username)
        if links:
            qr = generate_qr_code(links[0])
            await callback.message.answer_photo(
                photo=qr,
                caption="📱 <b>QR-код для подключения</b>\n\nОтсканируйте в приложении v2rayNG или Streisand.",
                parse_mode="HTML",
            )
        else:
            await callback.answer("❌ Ключи не найдены.", show_alert=True)
    except Exception:
        logger.error("Failed to generate QR", exc_info=True)
        await callback.answer("❌ Ошибка генерации QR-кода.", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "payment_history")
async def payment_history(callback: CallbackQuery):
    user_service = UserService()
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    # Явно загружаем платежи (избегаем N+1)
    async with async_session() as session:
        from app.models.payment import Payment
        result = await session.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .limit(10)
        )
        payments = result.scalars().all()

    if not payments:
        await callback.answer("📊 История платежей пуста.", show_alert=True)
        return

    history_text = "📊 <b>История платежей:</b>\n\n"
    for p in payments:
        status_emoji = "✅" if p.status == "success" else "⏳"
        date_str = p.created_at.strftime("%d.%m.%Y") if p.created_at else "—"
        history_text += (
            f"{status_emoji} {p.amount}₽ — {p.provider}\n"
            f"   {date_str}\n\n"
        )

    await callback.message.answer(history_text, parse_mode="HTML")
    await callback.answer()