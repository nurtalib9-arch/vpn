import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class CryptoBotPayment:
    def __init__(self):
        self.token = settings.CRYPTOBOT_TOKEN
        self.base_url = "https://pay.crypt.bot/api"

    async def create_invoice(
        self, amount: float, description: str, payload: str
    ) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/createInvoice",
                headers={"Crypto-Pay-API-Token": self.token},
                json={
                    "asset": "USDT",
                    "amount": str(amount),
                    "description": description,
                    "payload": payload,
                    "paid_btn_name": "callback",
                    "paid_btn_url": f"https://t.me/your_bot",
                    "allow_comments": False,
                    "allow_anonymous": False,
                },
            )
            response.raise_for_status()
            return response.json()["result"]

    async def get_invoice(self, invoice_ids: list[str]) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/getInvoices",
                headers={"Crypto-Pay-API-Token": self.token},
                params={"invoice_ids": ",".join(invoice_ids)},
            )
            response.raise_for_status()
            return response.json()["result"]["items"]
