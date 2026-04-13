from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .env import resolve_debug_dir

logger = logging.getLogger(__name__)


def try_save_screenshot(driver, name: str) -> Optional[str]:
    """Best-effort screenshot saving for debugging (no secrets logged)."""
    if driver is None:
        return None

    try:
        out_dir = resolve_debug_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in name)
        path = out_dir / safe_name
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            path = Path(str(path) + ".png")

        ok = driver.save_screenshot(str(path))
        if ok:
            logger.info("Saved Selenium screenshot: %s", path)
            return str(path)
    except Exception as exc:
        logger.debug("Failed to save screenshot: %s", exc)

    return None
