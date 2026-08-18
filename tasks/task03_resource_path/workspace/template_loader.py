"""Helpers for loading a bundled document template."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_template() -> dict[str, Any]:
    """Load the bundled template definition."""

    path = Path("assets/template.json")
    return json.loads(path.read_text(encoding="utf-8"))


def template_name() -> str:
    return str(load_template()["name"])


def template_category() -> str:
    return str(load_template()["category"])
