from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.services.payment_service import PaymentService
import hashlib
import hmac
import json
import logging

logger = logging.getLogger(__name__)

webhook_app = FastAPI(title="VPN Bot Webhooks")


async def _is_already_processed(provider_payment_id: str) -> bool:
    """Идемпотентная проверка — если платёж уже успешен, не обрабатываем повторно."""
    payment = await PaymentService().get_payment_by_provider_id(provider_payment_id)
    return payment is not None and payment.status == "success"


@webhook_app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        logger.error("YooKassa webhook: failed to parse JSON", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
        event = payload.get("event", "")

        if event == "payment.succeeded":
            obj = payload.get("object", {})
            if not obj:
                logger.warning("YooKassa webhook: empty 'object' field")
                return {"status": "ok"}

            payment_id = obj.get("id")
            if not payment_id:
                logger.warning("YooKassa webhook: no 'id' in object")
                return {"status": "ok"}

            # Используем наш internal ID из metadata, иначе YooKassa ID
            metadata = obj.get("metadata") or {}
            our_payment_id = metadata.get("payment_id") or payment_id

            logger.info(f"YooKassa webhook: payment.succeeded, id={our_payment_id}")

            # Идемпотентность: уже обработан?
            if await _is_already_processed(our_payment_id):
                logger.info(f"YooKassa webhook: {our_payment_id} already processed, skipping")
                return {"status": "ok"}

            payment_service = PaymentService()
            await payment_service.process_successful_payment(our_payment_id)

        return {"status": "ok"}
    except Exception:
        logger.error("YooKassa webhook processing failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@webhook_app.post("/webhook/cryptobot")
async def cryptobot_webhook(request: Request):
    try:
        body = await request.body()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read body")

    # Верификация подписи CryptoBot
    if settings.CRYPTOBOT_TOKEN:
        signature = request.headers.get("crypto-pay-api-signature", "")
        secret = hashlib.sha256(settings.CRYPTOBOT_TOKEN.encode()).digest()
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            logger.warning("CryptoBot webhook: invalid signature")
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
        update_type = payload.get("update_type", "")

        if update_type == "invoice_paid":
            invoice = payload.get("payload") or {}
            our_payment_id = invoice.get("payload", "")

            if not our_payment_id:
                logger.warning("CryptoBot webhook: no payload in invoice")
                return {"status": "ok"}

            logger.info(f"CryptoBot webhook: invoice_paid, payment_id={our_payment_id}")

            # Идемпотентность
            if await _is_already_processed(our_payment_id):
                logger.info(f"CryptoBot webhook: {our_payment_id} already processed, skipping")
                return {"status": "ok"}

            payment_service = PaymentService()
            await payment_service.process_successful_payment(our_payment_id)

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception:
        logger.error("CryptoBot webhook processing failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@webhook_app.post("/webhook/cloudpayments")
async def cloudpayments_webhook(request: Request):
    try:
        form = await request.form()
    except Exception:
        logger.error("CloudPayments webhook: failed to parse form", exc_info=True)
        return JSONResponse({"code": 13})

    try:
        status = form.get("Status", "")

        if status == "Completed":
            transaction_id = form.get("TransactionId", "")
            if not transaction_id:
                logger.warning("CloudPayments webhook: no TransactionId")
                return JSONResponse({"code": 0})

            our_payment_id = str(transaction_id)
            logger.info(f"CloudPayments webhook: Completed, id={our_payment_id}")

            # Идемпотентность
            if await _is_already_processed(our_payment_id):
                logger.info(f"CloudPayments webhook: {our_payment_id} already processed, skipping")
                return JSONResponse({"code": 0})

            payment_service = PaymentService()
            await payment_service.process_successful_payment(our_payment_id)

        return JSONResponse({"code": 0})
    except Exception:
        logger.error("CloudPayments webhook processing failed", exc_info=True)
        return JSONResponse({"code": 13})  # retry code


@webhook_app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Telegram bot webhook endpoint — handled by aiogram inside main app."""
    return {"ok": True}
