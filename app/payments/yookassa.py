import httpx
from app.core.config import settings
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class YooKassaPayment:
    def __init__(self):
        self.shop_id = settings.YOOKASSA_SHOP_ID
        self.secret_key = settings.YOOKASSA_SECRET_KEY
        self.base_url = "https://api.yookassa.ru/v3"

    async def create_payment(
        self,
        amount: float,
        description: str,
        return_url: str,
        metadata: Dict,
    ) -> Optional[Dict]:
        if not self.shop_id or not self.secret_key:
            logger.warning("YooKassa credentials not configured")
            return None

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/payments",
                auth=(self.shop_id, self.secret_key),
                headers={
                    "Idempotence-Key": metadata.get("payment_id", ""),
                    "Content-Type": "application/json",
                },
                json={
                    "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                    "capture": True,
                    "confirmation": {"type": "redirect", "return_url": return_url},
                    "description": description,
                    "metadata": metadata,
                },
            )

            if response.status_code in (200, 201):
                return response.json()

            logger.error(
                f"YooKassa payment creation failed: {response.status_code} {response.text}"
            )
            return None

    async def get_payment(self, payment_id: str) -> Optional[Dict]:
        if not self.shop_id or not self.secret_key:
            return None

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/payments/{payment_id}",
                auth=(self.shop_id, self.secret_key),
            )
            if response.status_code == 200:
                return response.json()
            return None
