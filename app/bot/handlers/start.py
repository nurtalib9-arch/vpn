from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from app.bot.keyboards.main_menu import get_main_menu, get_tariffs_menu
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    referral_code = args[0] if args else None

    user_service = UserService()
    user = await user_service.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        referral_code=referral_code,
    )

    if user.is_banned:
        await message.answer("⛔ Ваш аккаунт заблокирован.")
        return

    name = message.from_user.first_name or "пользователь"
    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        "Добро пожаловать в <b>VPN сервис</b>.\n\n"
        "Быстрое подключение. Никаких ограничений. Полная анонимность.\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu(),
        parse_mode="HTML",
    )


@router.message(F.text == "🛒 Купить подписку")
async def buy_subscription(message: Message):
    await message.answer(
        "📋 <b>Выберите тариф:</b>\n\n"
        "🔹 <b>1 месяц</b> — 249₽\n"
        "🔹 <b>3 месяца</b> — 669₽ <i>(-10%)</i>\n"
        "🔹 <b>6 месяцев</b> — 1 199₽ <i>(-20%)</i>\n"
        "🔹 <b>12 месяцев</b> — 1 899₽ <i>(-37%)</i>\n\n"
        "Выберите удобный вариант:",
        reply_markup=get_tariffs_menu(),
        parse_mode="HTML",
    )


@router.message(F.text == "❓ Помощь")
async def show_help(message: Message):
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "<b>Как пользоваться VPN?</b>\n"
        "1. Купите подписку\n"
        "2. Получите ключ в разделе «Мой профиль»\n"
        "3. Используйте приложение v2rayNG (Android) или Streisand (iOS)\n\n"
        "<b>Поддерживаемые протоколы:</b>\n"
        "• VLESS + Reality (рекомендуется)\n\n"
        "<b>Есть вопросы?</b> Напишите в поддержку: @support",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "buy")
async def buy_callback(callback: CallbackQuery):
    await callback.message.answer(
        "📋 <b>Выберите тариф:</b>",
        reply_markup=get_tariffs_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "renew")
async def renew_callback(callback: CallbackQuery):
    await callback.message.answer(
        "🔄 <b>Продление подписки</b>\n\nВыберите тариф:",
        reply_markup=get_tariffs_menu(),
        parse_mode="HTML",
    )
    await callback.answer()
