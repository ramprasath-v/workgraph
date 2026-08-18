"""Configuration-backed helpers for the second benchmark task."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_settings(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load settings, optionally from a caller-supplied path."""

    path = Path(config_path) if config_path else Path("config/settings.json")
    return json.loads(path.read_text(encoding="utf-8"))


def service_label() -> str:
    settings = load_settings()
    return f"{settings['service_name']}:{settings['environment']}"


def retry_limit() -> int:
    return int(load_settings()["retry_limit"])
