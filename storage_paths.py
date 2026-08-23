"""Resolve writable SQLite paths for local development."""
from __future__ import annotations

import os

_DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "data")


def resolve_sqlite_path(env_var: str, filename: str) -> str:
    """Prefer explicit env, then ./data. Do not use /tmp — local memory must survive restart."""
    explicit = os.environ.get(env_var, "").strip()
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    candidates.append(os.path.join(_DEFAULT_DIR, filename))

    seen: set[str] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        parent = os.path.dirname(path) or "."
        try:
            os.makedirs(parent, exist_ok=True)
            if os.access(parent, os.W_OK):
                return path
        except OSError:
            continue
    os.makedirs(_DEFAULT_DIR, exist_ok=True)
    return os.path.join(_DEFAULT_DIR, filename)
