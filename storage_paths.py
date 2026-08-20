"""Resolve writable SQLite paths on Render free tier (no /var/data disk)."""
from __future__ import annotations

import os

_RENDER_DISK_DIR = "/var/data"
_DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "data")


def resolve_sqlite_path(env_var: str, filename: str) -> str:
    """Pick first writable location; prefer explicit env, then /tmp, then ./data."""
    explicit = os.environ.get(env_var, "").strip()
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    candidates.append(os.path.join("/tmp", filename))
    candidates.append(os.path.join(_DEFAULT_DIR, filename))
    if os.path.isdir(_RENDER_DISK_DIR) and os.access(_RENDER_DISK_DIR, os.W_OK):
        candidates.append(os.path.join(_RENDER_DISK_DIR, filename))

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
    return os.path.join("/tmp", filename)
