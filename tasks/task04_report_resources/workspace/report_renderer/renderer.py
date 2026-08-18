"""Render compact status reports using external formatting defaults."""

from __future__ import annotations

from pathlib import Path

from .loader import load_render_defaults


def render_report(
    title: str,
    status: str = "draft",
    resource_directory: str | Path | None = None,
) -> str:
    """Render a report while allowing callers to override its resources."""

    defaults = load_render_defaults(resource_directory)
    label = defaults["status_labels"][status]
    return "\n".join(
        (
            f"{defaults['heading_marker']} {title}",
            f"Status: {label}",
            defaults["footer"],
        )
    )
