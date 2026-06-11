from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from app.bot.keyboards.main_menu import get_payment_methods_menu, get_tariffs_menu, TARIFF_PRICES
from app.services.payment_service import PaymentService
from app.services.user_service import UserService
from app.core.config import settings
from app.payments.yookassa import YooKassaPayment
from app.payments.cryptobot import CryptoBotPayment
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)
router = Router()

# Tariff id -> duration in months
TARIFF_MONTHS = {1: 1, 3: 3, 6: 6, 12: 12}


@router.callback_query(F.data.startswith("tariff_"))
async def process_tariff(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[1])
    name, price = TARIFF_PRICES.get(tariff_id, ("?", "?"))

    await callback.message.edit_text(
        f"💳 <b>Тариф: {name} — {price}₽</b>\n\n"
        "Выберите способ оплаты:",
        reply_markup=get_payment_methods_menu(tariff_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: CallbackQuery):
    await callback.message.edit_text(
        "📋 <b>Выберите тариф:</b>",
        reply_markup=get_tariffs_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_card_"))
async def process_card_payment(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[2])
    name, price_str = TARIFF_PRICES.get(tariff_id, ("?", "0"))
    amount = Decimal(price_str.replace(" ", "").replace(",", "."))

    user_service = UserService()
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    payment_service = PaymentService()
    payment = await payment_service.create_payment(
        user_id=user.id,
        amount=amount,
        provider="yookassa",
        tariff_id=tariff_id,
    )

    # Try to create YooKassa payment link
    yookassa = YooKassaPayment()
    payment_data = None
    if yookassa.shop_id and yookassa.secret_key:
        payment_data = await yookassa.create_payment(
            amount=float(amount),
            description=f"VPN подписка {name}",
            return_url=f"https://t.me/{(await callback.bot.get_me()).username}",
            metadata={"payment_id": payment.provider_payment_id, "tariff_id": tariff_id},
        )

    if payment_data and payment_data.get("confirmation"):
        confirm_url = payment_data["confirmation"].get("confirmation_url", "")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=confirm_url)],
        ])
        await callback.message.edit_text(
            f"✅ <b>Счёт создан</b>\n\n"
            f"Тариф: <b>{name}</b>\n"
            f"Сумма: <b>{price_str}₽</b>\n\n"
            "Нажмите кнопку для оплаты.\n"
            "<i>После оплаты подписка активируется автоматически.</i>",
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            f"✅ <b>Счёт создан</b>\n\n"
            f"Тариф: <b>{name}</b>\n"
            f"Сумма: <b>{price_str}₽</b>\n"
            f"ID платежа: <code>{payment.provider_payment_id}</code>\n\n"
            "После оплаты подписка будет активирована автоматически.\n\n"
            "<i>⚠️ YooKassa не настроена — обратитесь к администратору.</i>",
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_crypto_"))
async def process_crypto_payment(callback: CallbackQuery):
    tariff_id = int(callback.data.split("_")[2])
    name, price_str = TARIFF_PRICES.get(tariff_id, ("?", "0"))
    amount_rub = float(price_str.replace(" ", "").replace(",", "."))

    # БАГ 8: используем динамический курс из конфига (можно обновлять)
    # Конвертируем RUB в USDT используя текущий курс из settings
    amount_usdt = round(amount_rub / settings.USD_TO_RUB_RATE, 2)

    user_service = UserService()
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    payment_service = PaymentService()
    payment = await payment_service.create_payment(
        user_id=user.id,
        amount=Decimal(str(amount_rub)),
        provider="cryptobot",
        tariff_id=tariff_id,
    )

    cryptobot = CryptoBotPayment()
    if cryptobot.token:
        try:
            invoice = await cryptobot.create_invoice(
                amount=amount_usdt,
                description=f"VPN подписка {name}",
                payload=payment.provider_payment_id,
            )
            pay_url = invoice.get("bot_invoice_url", "")
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="₿ Оплатить криптовалютой", url=pay_url)],
            ])
            await callback.message.edit_text(
                f"₿ <b>Оплата криптовалютой</b>\n\n"
                f"Тариф: <b>{name}</b>\n"
                f"Сумма: <b>{amount_usdt} USDT</b>\n\n"
                "Нажмите кнопку для оплаты через CryptoBot:",
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception:
            logger.error("CryptoBot invoice creation failed", exc_info=True)
            await callback.message.edit_text(
                "❌ Ошибка создания крипто-платежа. Попробуйте позже.",
                parse_mode="HTML",
            )
    else:
        await callback.message.edit_text(
            f"₿ <b>Оплата криптовалютой</b>\n\n"
            f"Тариф: <b>{name}</b>\n"
            f"ID платежа: <code>{payment.provider_payment_id}</code>\n\n"
            "<i>⚠️ CryptoBot не настроен — обратитесь к администратору.</i>",
            parse_mode="HTML",
        )
    await callback.answer()