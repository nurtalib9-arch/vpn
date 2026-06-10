import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class CloudPayments:
    def __init__(self):
        self.public_id = settings.CLOUDPAYMENTS_PUBLIC_ID
        self.api_secret = settings.CLOUDPAYMENTS_API_SECRET
        self.base_url = "https://api.cloudpayments.ru"

    async def create_payment(
        self, amount: float, description: str, currency: str = "RUB"
    ) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/payments/cryptogram",
                auth=(self.public_id, self.api_secret),
                json={
                    "Amount": amount,
                    "Currency": currency,
                    "Description": description,
                },
            )
            return response.json()

    async def check_payment(self, transaction_id: int) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/payments/get",
                auth=(self.public_id, self.api_secret),
                json={"TransactionId": transaction_id},
            )
            return response.json()
