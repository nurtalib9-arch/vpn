from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.bot.keyboards.main_menu import get_gift_tariffs_menu, get_gift_payment_menu, TARIFF_PRICES
from app.services.user_service import UserService
from app.services.payment_service import PaymentService
from app.payments.yookassa import YooKassaPayment
from app.payments.cryptobot import CryptoBotPayment
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)
router = Router()


class GiftStates(StatesGroup):
    waiting_for_recipient = State()
    waiting_for_tariff = State()


@router.message(F.text == "🎁 Подарить подписку")
async def gift_start(message: Message, state: FSMContext):
    await state.set_state(GiftStates.waiting_for_recipient)
    await message.answer(
        "🎁 <b>Подарить подписку</b>\n\n"
        "Введите Telegram ID или @username получателя подарка:",
        parse_mode="HTML",
    )


@router.message(GiftStates.waiting_for_recipient)
async def gift_recipient(message: Message, state: FSMContext):
    text = message.text.strip()

    user_service = UserService()

    # Try by @username
    if text.startswith("@"):
        username = text[1:]
        # Search by username stored in DB
        from sqlalchemy import select
        from app.core.database import async_session
        from app.models.user import User
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            recipient = result.scalar_one_or_none()
    else:
        # Try by telegram_id
        try:
            tg_id = int(text)
            recipient = await user_service.get_user_by_telegram_id(tg_id)
        except ValueError:
            await message.answer("❌ Неверный формат. Введите Telegram ID (число) или @username.")
            return

    if not recipient:
        await message.answer(
            "❌ Пользователь не найден в системе.\n\n"
            "Получатель должен быть зарегистрирован в боте. "
            "Попросите его написать /start и попробуйте снова."
        )
        return

    sender = await user_service.get_user_by_telegram_id(message.from_user.id)
    if sender and recipient.id == sender.id:
        await message.answer("❌ Нельзя подарить подписку самому себе.")
        return

    await state.update_data(recipient_id=recipient.id, recipient_name=recipient.first_name or f"ID {recipient.telegram_id}")
    await state.set_state(GiftStates.waiting_for_tariff)

    recipient_display = f"@{recipient.username}" if recipient.username else f"{recipient.first_name or 'пользователь'}"
    await message.answer(
        f"✅ Получатель: <b>{recipient_display}</b>\n\n"
        "Выберите тариф для подарка:",
        reply_markup=get_gift_tariffs_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("gift_tariff_"))
async def gift_tariff_selected(callback: CallbackQuery, state: FSMContext):
    tariff_id = int(callback.data.split("_")[2])
    name, price = TARIFF_PRICES.get(tariff_id, ("?", "?"))

    await state.update_data(gift_tariff_id=tariff_id)

    data = await state.get_data()
    recipient_name = data.get("recipient_name", "получатель")

    await callback.message.edit_text(
        f"🎁 <b>Подарок для {recipient_name}</b>\n\n"
        f"Тариф: <b>{name}</b> — {price}₽\n\n"
        "Выберите способ оплаты:",
        reply_markup=get_gift_payment_menu(tariff_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_gift_tariffs")
async def back_to_gift_tariffs(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите тариф для подарка:",
        reply_markup=get_gift_tariffs_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gift_pay_card_"))
async def gift_pay_card(callback: CallbackQuery, state: FSMContext):
    tariff_id = int(callback.data.split("_")[3])
    name, price_str = TARIFF_PRICES.get(tariff_id, ("?", "0"))
    amount = Decimal(price_str.replace(" ", "").replace(",", "."))

    state_data = await state.get_data()
    recipient_id = state_data.get("recipient_id")

    user_service = UserService()
    sender = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if not sender:
        await callback.answer("❌ Ошибка.", show_alert=True)
        return

    payment_service = PaymentService()
    payment = await payment_service.create_payment(
        user_id=sender.id,
        amount=amount,
        provider="yookassa_gift",
        tariff_id=tariff_id,
    )

    # Patch metadata to include gift recipient
    from sqlalchemy import update
    from app.core.database import async_session
    from app.models.payment import Payment
    async with async_session() as session:
        meta = json.loads(payment.metadata_json or "{}")
        meta["gift_recipient_id"] = recipient_id
        await session.execute(
            update(Payment)
            .where(Payment.id == payment.id)
            .values(metadata_json=json.dumps(meta))
        )
        await session.commit()

    yookassa = YooKassaPayment()
    payment_data = None
    if yookassa.shop_id and yookassa.secret_key:
        payment_data = await yookassa.create_payment(
            amount=float(amount),
            description=f"Подарочная VPN подписка {name}",
            return_url=f"https://t.me/{(await callback.bot.get_me()).username}",
            metadata={"payment_id": payment.provider_payment_id, "tariff_id": tariff_id, "gift": True},
        )

    await state.clear()

    if payment_data and payment_data.get("confirmation"):
        confirm_url = payment_data["confirmation"].get("confirmation_url", "")
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=confirm_url)],
        ])
        await callback.message.edit_text(
            f"🎁 <b>Подарок создан!</b>\n\n"
            f"Тариф: <b>{name}</b> — {price_str}₽\n\n"
            "После оплаты подписка будет активирована получателю.",
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            f"🎁 <b>Подарок создан!</b>\n\n"
            f"Тариф: <b>{name}</b> — {price_str}₽\n"
            f"ID: <code>{payment.provider_payment_id}</code>\n\n"
            "<i>⚠️ YooKassa не настроена — обратитесь к администратору.</i>",
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("gift_pay_crypto_"))
async def gift_pay_crypto(callback: CallbackQuery, state: FSMContext):
    tariff_id = int(callback.data.split("_")[3])
    name, price_str = TARIFF_PRICES.get(tariff_id, ("?", "0"))
    amount_rub = float(price_str.replace(" ", "").replace(",", "."))
    amount_usdt = round(amount_rub / 90, 2)

    state_data = await state.get_data()
    recipient_id = state_data.get("recipient_id")

    user_service = UserService()
    sender = await user_service.get_user_by_telegram_id(callback.from_user.id)
    if not sender:
        await callback.answer("❌ Ошибка.", show_alert=True)
        return

    payment_service = PaymentService()
    payment = await payment_service.create_payment(
        user_id=sender.id,
        amount=Decimal(str(amount_rub)),
        provider="cryptobot_gift",
        tariff_id=tariff_id,
    )

    from sqlalchemy import update
    from app.core.database import async_session
    from app.models.payment import Payment as PaymentModel
    async with async_session() as session:
        meta = json.loads(payment.metadata_json or "{}")
        meta["gift_recipient_id"] = recipient_id
        await session.execute(
            update(PaymentModel)
            .where(PaymentModel.id == payment.id)
            .values(metadata_json=json.dumps(meta))
        )
        await session.commit()

    await state.clear()

    cryptobot = CryptoBotPayment()
    if cryptobot.token:
        try:
            invoice = await cryptobot.create_invoice(
                amount=amount_usdt,
                description=f"Подарочная VPN подписка {name}",
                payload=payment.provider_payment_id,
            )
            pay_url = invoice.get("bot_invoice_url", "")
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="₿ Оплатить криптовалютой", url=pay_url)],
            ])
            await callback.message.edit_text(
                f"🎁 <b>Подарок создан!</b>\n\n"
                f"Тариф: <b>{name}</b> — {amount_usdt} USDT\n\n"
                "После оплаты подписка будет активирована получателю.",
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception:
            logger.error("CryptoBot gift invoice failed", exc_info=True)
            await callback.message.edit_text("❌ Ошибка создания крипто-платежа.")
    else:
        await callback.message.edit_text(
            f"🎁 <b>Подарок создан!</b>\n\n"
            f"ID: <code>{payment.provider_payment_id}</code>\n\n"
            "<i>⚠️ CryptoBot не настроен.</i>",
            parse_mode="HTML",
        )
    await callback.answer()
