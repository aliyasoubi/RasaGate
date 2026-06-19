"""Rasa lifecycle: startup readiness wait and model preload."""
import asyncio
import logging
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.exceptions import RasaUnreachableError

logger = logging.getLogger(__name__)

_READY_RETRY_DELAY_SECONDS = 2.0


async def wait_for_rasa(client: httpx.AsyncClient, max_retries: int = 30) -> None:
    """Block until the Rasa server reports ready."""
    url = f"{settings.rasa_url}/status"

    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                logger.info("Rasa server is ready")
                return
        except httpx.RequestError:
            pass

        if attempt < max_retries:
            logger.info("Waiting for Rasa... (%d/%d)", attempt, max_retries)
            await asyncio.sleep(_READY_RETRY_DELAY_SECONDS)

    raise RasaUnreachableError(
        f"Rasa server did not become ready after {max_retries} attempts"
    )


def _find_latest_model(models_dir: Path) -> Path | None:
    if not models_dir.exists():
        logger.warning("No models directory at %s. Skipping preload.", models_dir)
        return None

    model_files = sorted(
        models_dir.glob("*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not model_files:
        logger.warning("No trained models found. Agent idle until first training.")
        return None
    return model_files[0]


async def load_latest_model(client: httpx.AsyncClient) -> None:
    """Load the most recent trained model into Rasa at startup."""
    latest = _find_latest_model(Path(settings.rasa_model_path))
    if latest is None:
        return

    logger.info("Loading model: %s", latest.name)
    try:
        resp = await client.put(
            f"{settings.rasa_url}/model",
            json={"model_file": str(latest.absolute())},
            timeout=30.0,
        )
        resp.raise_for_status()
        logger.info("Model %s loaded successfully", latest.name)
    except httpx.HTTPError as exc:
        logger.error("Failed to load model: %s", exc)
        raise RasaUnreachableError(f"Could not load model into Rasa: {exc}") from exc


async def initialize_rasa_agent(client: httpx.AsyncClient) -> None:
    """Wait for readiness, then preload the latest model if present."""
    await wait_for_rasa(client)
    await load_latest_model(client)
