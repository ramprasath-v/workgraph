"""Load rendering defaults from bundled or caller-supplied resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _defaults_path(resource_directory: str | Path | None) -> Path:
    directory = (
        Path(resource_directory)
        if resource_directory is not None
        else Path("report_renderer/resources")
    )
    return directory / "defaults.json"


def load_render_defaults(
    resource_directory: str | Path | None = None,
) -> dict[str, Any]:
    """Load the report formatting defaults."""

    path = _defaults_path(resource_directory)
    return json.loads(path.read_text(encoding="utf-8"))
