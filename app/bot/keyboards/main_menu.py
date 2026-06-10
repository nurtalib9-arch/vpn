from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ─── Prices map (also used in handlers) ───────────────────────────────────────
TARIFF_PRICES = {
    1: ("1 месяц", "249.00"),
    3: ("3 месяца", "669.00"),
    6: ("6 месяцев", "1 199.00"),
    12: ("12 месяцев", "1 899.00"),
}


def get_main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🛒 Купить подписку")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="🎁 Подарить подписку")],
        [KeyboardButton(text="👥 Реферальная система"), KeyboardButton(text="❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def get_tariffs_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="1 мес — 249₽", callback_data="tariff_1")],
        [InlineKeyboardButton(text="3 мес — 669₽ (-10%)", callback_data="tariff_3")],
        [InlineKeyboardButton(text="6 мес — 1 199₽ (-20%)", callback_data="tariff_6")],
        [InlineKeyboardButton(text="12 мес — 1 899₽ (-37%)", callback_data="tariff_12")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_payment_methods_menu(tariff_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="💳 СБП / Банковская карта", callback_data=f"pay_card_{tariff_id}")],
        [InlineKeyboardButton(text="₿ Криптовалюта (USDT)", callback_data=f"pay_crypto_{tariff_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tariffs")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_profile_menu(has_subscription: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_subscription:
        buttons.append([InlineKeyboardButton(text="🔑 Получить ключ", callback_data="get_key")])
        buttons.append([InlineKeyboardButton(text="📱 QR-код", callback_data="get_qr")])
        buttons.append([InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew")])
    else:
        buttons.append([InlineKeyboardButton(text="🛒 Купить подписку", callback_data="buy")])
    buttons.append([InlineKeyboardButton(text="📊 История платежей", callback_data="payment_history")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_gift_tariffs_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="1 мес — 249₽", callback_data="gift_tariff_1")],
        [InlineKeyboardButton(text="3 мес — 669₽ (-10%)", callback_data="gift_tariff_3")],
        [InlineKeyboardButton(text="6 мес — 1 199₽ (-20%)", callback_data="gift_tariff_6")],
        [InlineKeyboardButton(text="12 мес — 1 899₽ (-37%)", callback_data="gift_tariff_12")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_gift_payment_menu(tariff_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="💳 СБП / Банковская карта", callback_data=f"gift_pay_card_{tariff_id}")],
        [InlineKeyboardButton(text="₿ Криптовалюта (USDT)", callback_data=f"gift_pay_crypto_{tariff_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_gift_tariffs")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel"),
        ]
    ])
