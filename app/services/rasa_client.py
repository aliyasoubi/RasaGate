# app/services/rasa_client.py
from typing import Any
import httpx
from app.core.config import settings
from app.core.exceptions import RasaUnreachableError


class RasaClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str | None = None) -> None:
        self._client = client
        self.base_url = (base_url or settings.rasa_url).rstrip("/")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            resp = await self._client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            raise RasaUnreachableError(
                f"Rasa returned {exc.response.status_code} for {path}."
            ) from exc
        except httpx.RequestError as exc:
            raise RasaUnreachableError(f"Cannot reach Rasa at {url}: {exc}") from exc

    async def send_message(self, sender_id: str, message: str) -> list[dict[str, Any]]:
        resp = await self._request(
            "POST", "/webhooks/rest/webhook",
            json={"sender": sender_id, "message": message},
        )
        return resp.json()

    async def train(self, training_data: str, timeout: float = 600.0) -> bytes:
        resp = await self._request(
            "POST", "/model/train",
            content=training_data.encode("utf-8"),
            headers={"Content-Type": "application/yaml"},
            timeout=timeout,  # per-call override for the long training POST
        )
        return resp.content

    async def replace_model(self, model_path: str) -> None:
        await self._request("PUT", "/model", json={"model_file": model_path})
