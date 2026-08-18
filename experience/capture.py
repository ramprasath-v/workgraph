"""Derive experience evidence by comparing pristine and active workspaces."""

from __future__ import annotations

import difflib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schema import ExperienceRecord, Verification


IGNORED_DIRECTORIES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
IGNORED_FILENAMES = {".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".swp", ".tmp", ".temp"}


def _is_ignored(relative_path: Path) -> bool:
    return (
        any(part in IGNORED_DIRECTORIES for part in relative_path.parts)
        or relative_path.name in IGNORED_FILENAMES
        or relative_path.name.endswith("~")
        or relative_path.suffix in IGNORED_SUFFIXES
    )


def _workspace_files(root: Path) -> dict[str, bytes]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"workspace is not a directory: {root}")
    files: dict[str, bytes] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if _is_ignored(relative) or path.is_symlink() or not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if root not in resolved.parents:
            raise ValueError(f"file escapes workspace: {relative.as_posix()}")
        files[relative.as_posix()] = resolved.read_bytes()
    return files


def _file_diff(path: str, before: bytes | None, after: bytes | None) -> str:
    before_name = f"a/{path}" if before is not None else "/dev/null"
    after_name = f"b/{path}" if after is not None else "/dev/null"
    try:
        before_text = before.decode("utf-8") if before is not None else ""
        after_text = after.decode("utf-8") if after is not None else ""
    except UnicodeDecodeError:
        return f"Binary files {before_name} and {after_name} differ\n"
    return "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=before_name,
            tofile=after_name,
        )
    )


def compare_workspaces(pristine: Path, active: Path) -> tuple[list[str], str]:
    """Return sorted changed paths and a unified diff derived from file bytes."""

    pristine_files = _workspace_files(pristine)
    active_files = _workspace_files(active)
    changed = sorted(
        path
        for path in pristine_files.keys() | active_files.keys()
        if pristine_files.get(path) != active_files.get(path)
    )
    patch = "".join(
        _file_diff(path, pristine_files.get(path), active_files.get(path))
        for path in changed
    )
    return changed, patch


def capture_experience(
    *,
    pristine_workspace: Path,
    active_workspace: Path,
    task_id: str,
    producer_model: str,
    problem: str,
    environment: dict[str, str],
    verification_command: list[str],
    passed: int,
    failed: int,
    successful: bool,
    experiences_dir: Path,
    created_at: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    experience_id: str | None = None,
) -> tuple[ExperienceRecord, Path] | None:
    """Persist observed evidence only for a deterministically successful run."""

    if not successful:
        return None
    files_changed, patch = compare_workspaces(
        pristine_workspace, active_workspace
    )
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    record = ExperienceRecord(
        experience_id=experience_id or f"exp_{uuid.uuid4().hex}",
        task_id=task_id,
        producer_model=producer_model,
        problem=problem,
        environment=dict(environment),
        files_changed=files_changed,
        patch=patch,
        verification=Verification(
            command=list(verification_command), passed=passed, failed=failed
        ),
        successful=True,
        started_at=started_at or created_at,
        completed_at=completed_at or created_at,
        created_at=created_at,
    )
    return record, record.write_json(experiences_dir)
