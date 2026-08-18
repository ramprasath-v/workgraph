"""Provider-neutral filtering of action fields before strict validation."""

from __future__ import annotations

from typing import Any

from .tools import WorkspaceTools


def normalize_action(raw_action: Any) -> Any:
    """Discard fields irrelevant to a known action without repairing values."""

    if not isinstance(raw_action, dict):
        return raw_action
    name = raw_action.get("action")
    fields = WorkspaceTools.ACTION_FIELDS.get(name)
    if fields is None:
        return dict(raw_action)
    return {field: raw_action[field] for field in fields if field in raw_action}
