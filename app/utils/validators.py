import re


def validate_referral_code(code: str) -> bool:
    pattern = r"^[a-zA-Z0-9]{8}$"
    return bool(re.match(pattern, code))


def validate_telegram_id(telegram_id: str) -> bool:
    try:
        tid = int(telegram_id)
        return tid > 0
    except ValueError:
        return False
