"""Webhook notification for training events."""
import logging
import httpx

logger = logging.getLogger(__name__)


class NotificationService:
    async def notify_success(
        self, webhook_url: str, task_id: str, model_filename: str | None
    ) -> None:
        await self._post(
            webhook_url,
            {
                "task_id": task_id,
                "event": "training_completed",
                "status": "success",
                "details": {"model_file": model_filename},
            },
        )

    async def notify_failure(self, webhook_url: str, task_id: str, error: str) -> None:
        await self._post(
            webhook_url,
            {
                "task_id": task_id,
                "event": "training_failed",
                "status": "failed",
                "details": {"message": error},
            },
        )

    async def _post(self, url: str, payload: dict) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Webhook delivery failed for %s: %s", url, exc)
