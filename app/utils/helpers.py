def format_duration(days: int) -> str:
    if days >= 365:
        years = days // 365
        return f"{years} год" if years == 1 else f"{years} года"
    elif days >= 30:
        months = days // 30
        if months == 1:
            return "1 месяц"
        elif months < 5:
            return f"{months} месяца"
        return f"{months} месяцев"
    else:
        if days == 1:
            return "1 день"
        elif days < 5:
            return f"{days} дня"
        return f"{days} дней"


def format_price(amount: float) -> str:
    return f"{amount:,.0f}₽".replace(",", " ")
