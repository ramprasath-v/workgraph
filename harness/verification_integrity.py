"""Forward-looking protected-evaluator integrity checks for benchmark runs."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Iterable


INTEGRITY_GUARD_VERSION = "1.0"


def validate_protected_files(paths: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in paths:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("protected evaluator paths must be non-empty strings")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value != path.as_posix():
            raise ValueError(f"unsafe protected evaluator path: {value!r}")
        if value in normalized:
            raise ValueError(f"duplicate protected evaluator path: {value}")
        normalized.append(value)
    if not normalized:
        raise ValueError("at least one protected evaluator file is required")
    return tuple(normalized)


def capture_evaluator_hashes(
    workspace: Path,
    protected_files: Iterable[str],
    *,
    require_existing: bool,
) -> dict[str, str | None]:
    workspace = workspace.resolve()
    hashes: dict[str, str | None] = {}
    for relative in validate_protected_files(protected_files):
        candidate = workspace / relative
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            if require_existing:
                raise ValueError(f"protected evaluator file does not exist: {relative}")
            hashes[relative] = None
            continue
        if resolved != workspace and workspace not in resolved.parents:
            raise ValueError(f"protected evaluator escapes workspace: {relative}")
        if not resolved.is_file():
            raise ValueError(f"protected evaluator is not a regular file: {relative}")
        hashes[relative] = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return hashes


def modified_protected_files(
    original: dict[str, str | None], final: dict[str, str | None]
) -> list[str]:
    if original.keys() != final.keys():
        raise ValueError("protected evaluator hash sets differ")
    return sorted(path for path in original if original[path] != final[path])
