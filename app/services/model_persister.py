"""Persists trained models to disk."""
from datetime import datetime, timezone
from pathlib import Path


class ModelPersister:
    def __init__(self, models_dir: Path):
        self._models_dir = models_dir

    def save_model(self, model_bytes: bytes) -> Path:
        """Write model bytes to timestamped file."""
        self._models_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        model_path = self._models_dir / f"{timestamp}-latest.tar.gz"
        model_path.write_bytes(model_bytes)
        return model_path
