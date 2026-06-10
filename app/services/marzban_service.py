import httpx
import uuid
import asyncio
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Retry config
_MAX_RETRIES = 3
_RETRY_DELAYS = [1.0, 2.0, 4.0]  # экспоненциальный backoff


class MarzbanService:
    """
    Singleton-совместимый сервис для Marzban API.
    Держит один переиспользуемый AsyncClient вместо создания нового на каждый запрос.
    """

    def __init__(self):
        self.base_url = settings.MARZBAN_URL.rstrip("/")
        self.username = settings.MARZBAN_USERNAME
        self.password = settings.MARZBAN_PASSWORD
        self._token: str | None = None
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Баг 4: переиспользуемый клиент вместо нового на каждый запрос."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                verify=not settings.MARZBAN_INSECURE,
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=5.0),
            )
        return self._client

    async def close(self):
        """Вызвать при завершении работы приложения."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _get_token(self) -> str:
        """Получить/обновить токен. Кэшируется в памяти сервиса."""
        if self._token:
            return self._token

        client = await self._get_client()
        response = await client.post(
            f"{self.base_url}/api/admin/token",
            data={"username": self.username, "password": self.password},
        )
        response.raise_for_status()
        self._token = response.json()["access_token"]
        return self._token

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Баг 9: retry logic с экспоненциальным backoff.
        Повторяет запрос при сетевых ошибках и 5xx (не при 4xx).
        """
        client = await self._get_client()
        token = await self._get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        last_exc: Exception | None = None
        for attempt, delay in enumerate(
            [0.0] + _RETRY_DELAYS, start=1
        ):
            if delay:
                logger.warning(f"Marzban retry {attempt}/{_MAX_RETRIES}: {method} {path}")
                await asyncio.sleep(delay)

            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    **kwargs,
                )
                # Не ретраить клиентские ошибки (400, 404, 409...)
                if response.status_code < 500:
                    response.raise_for_status()
                    return response

                # 5xx — ретраить
                last_exc = httpx.HTTPStatusError(
                    f"Server error {response.status_code}",
                    request=response.request,
                    response=response,
                )
                logger.warning(
                    f"Marzban {response.status_code} on {method} {path}, will retry"
                )

            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as exc:
                last_exc = exc
                logger.warning(
                    f"Marzban network error on {method} {path}: {exc!r}"
                )
                # Сбрасываем токен при коннект-ошибке — возможно истёк
                self._token = None

        raise last_exc  # исчерпали все попытки

    # ─── Public API ───────────────────────────────────────────────────────────

    async def create_user(self, username: str, expire_days: int = 30) -> dict:
        user_uuid = str(uuid.uuid4())
        response = await self._request_with_retry(
            "POST",
            "/api/user",
            json={
                "username": username,
                "expire": expire_days * 86400,
                "data_limit": 0,
                "proxies": {
                    "vless": {"id": user_uuid, "flow": "xtls-rprx-vision"}
                },
                "inbounds": {"vless": ["VLESS Reality TCP"]},
            },
        )
        return response.json()

    async def get_user_config(self, username: str) -> dict:
        response = await self._request_with_retry("GET", f"/api/user/{username}")
        return response.json()

    async def get_user_links(self, username: str) -> list[str]:
        try:
            config = await self.get_user_config(username)
            return config.get("links", [])
        except Exception:
            logger.error(f"Failed to get links for {username}", exc_info=True)
            return []

    async def get_user_subscription_url(self, username: str) -> str:
        client = await self._get_client()
        token = await self._get_token()
        response = await client.get(
            f"{self.base_url}/api/user/{username}/subscription",
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=False,
        )
        return response.headers.get("location", "")

    async def disable_user(self, username: str) -> dict:
        response = await self._request_with_retry(
            "PUT", f"/api/user/{username}", json={"status": "disabled"}
        )
        return response.json()

    async def enable_user(self, username: str) -> dict:
        response = await self._request_with_retry(
            "PUT", f"/api/user/{username}", json={"status": "active"}
        )
        return response.json()

    async def delete_user(self, username: str) -> bool:
        try:
            response = await self._request_with_retry(
                "DELETE", f"/api/user/{username}"
            )
            return response.status_code == 200
        except Exception:
            return False

    async def get_system_stats(self) -> dict:
        response = await self._request_with_retry("GET", "/api/system")
        return response.json()

    async def reset_token(self):
        """Принудительный сброс токена (при 401 от API)."""
        self._token = None
