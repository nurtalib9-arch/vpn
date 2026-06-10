from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: List[int]

    DATABASE_URL: str
    REDIS_URL: str

    MARZBAN_URL: str
    MARZBAN_USERNAME: str
    MARZBAN_PASSWORD: str
    MARZBAN_INSECURE: bool = False

    YOOKASSA_SHOP_ID: Optional[str] = None
    YOOKASSA_SECRET_KEY: Optional[str] = None
    YOOKASSA_CALLBACK_URL: Optional[str] = None

    CLOUDPAYMENTS_PUBLIC_ID: Optional[str] = None
    CLOUDPAYMENTS_API_SECRET: Optional[str] = None
    CLOUDPAYMENTS_CALLBACK_URL: Optional[str] = None

    CRYPTOBOT_TOKEN: Optional[str] = None
    CRYPTOBOT_CALLBACK_URL: Optional[str] = None

    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    BOT_DOMAIN: str

    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    WEBHOOK_URL: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
