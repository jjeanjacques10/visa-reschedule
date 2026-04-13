from __future__ import annotations

import os
from pathlib import Path


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "1", "yes", "y")


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def resolve_debug_dir() -> Path:
    configured = os.environ.get("SELENIUM_DEBUG_DIR", "").strip()
    if configured:
        return Path(configured)

    # Lambda typically only allows writing to /tmp.
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp") / "selenium"

    return Path.cwd() / "artifacts" / "selenium"
