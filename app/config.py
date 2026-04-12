"""
Centralised configuration loader for the Visa Reschedule application.

Loads environment variables from a `.env` file (if present) via python-dotenv,
then exposes them as typed attributes with sensible defaults.
Call ``load_config()`` once at the entry point of each component (Flask app,
Telegram bot, Lambda handlers).  Subsequent imports of the module share the
same singleton ``Config`` instance.

Missing *required* variables are reported clearly rather than causing
cryptic ``KeyError`` / ``None`` failures downstream.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _find_env_file() -> Optional[Path]:
    """Walk up from the current working directory looking for a .env file."""
    search = Path.cwd()
    for _ in range(5):  # max 5 levels up
        candidate = search / ".env"
        if candidate.is_file():
            return candidate
        parent = search.parent
        if parent == search:
            break
        search = parent
    return None


def load_config(env_file: Optional[str] = None) -> None:
    """
    Load environment variables from *env_file* (or auto-detected ``.env``).

    Safe to call multiple times; dotenv will not overwrite already-set vars
    by default.
    """
    path: Optional[Path] = None
    if env_file:
        path = Path(env_file)
    else:
        path = _find_env_file()

    if path and path.is_file():
        load_dotenv(dotenv_path=path, override=False)
        logger.debug("Loaded environment variables from %s", path)
    else:
        # In production Lambda, variables come from the runtime environment;
        # the absence of a .env file is normal and not an error.
        logger.debug("No .env file found; relying on process environment variables")


class Config:
    """
    Read-only view of all configuration values used by the application.

    Instantiate after calling ``load_config()`` so dotenv values are in place.
    Accessing a *required* variable that is unset raises ``RuntimeError`` with
    a descriptive message instead of returning ``None`` silently.
    """

    # ------------------------------------------------------------------
    # AWS
    # ------------------------------------------------------------------

    @property
    def aws_region(self) -> str:
        return os.environ.get("AWS_REGION", "us-east-1")

    @property
    def aws_access_key_id(self) -> Optional[str]:
        return os.environ.get("AWS_ACCESS_KEY_ID")

    @property
    def aws_secret_access_key(self) -> Optional[str]:
        return os.environ.get("AWS_SECRET_ACCESS_KEY")

    # ------------------------------------------------------------------
    # DynamoDB
    # ------------------------------------------------------------------

    @property
    def dynamodb_users_table(self) -> str:
        return os.environ.get("DYNAMODB_USERS_TABLE", "visa-reschedule-users")

    @property
    def dynamodb_appointments_table(self) -> str:
        return os.environ.get(
            "DYNAMODB_APPOINTMENTS_TABLE", "visa-reschedule-appointments"
        )

    @property
    def dynamodb_endpoint_url(self) -> Optional[str]:
        """LocalStack or custom endpoint. ``None`` → use real AWS."""
        return os.environ.get("DYNAMODB_ENDPOINT_URL") or None

    # ------------------------------------------------------------------
    # SQS
    # ------------------------------------------------------------------

    @property
    def appointment_queue_url(self) -> str:
        value = os.environ.get("APPOINTMENT_QUEUE_URL", "")
        if not value:
            raise RuntimeError(
                "Required environment variable 'APPOINTMENT_QUEUE_URL' is not set. "
                "Set it in your .env file or process environment."
            )
        return value

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------

    @property
    def telegram_bot_token(self) -> str:
        value = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not value:
            raise RuntimeError(
                "Required environment variable 'TELEGRAM_BOT_TOKEN' is not set. "
                "Set it in your .env file or process environment."
            )
        return value

    # ------------------------------------------------------------------
    # Flask
    # ------------------------------------------------------------------

    @property
    def flask_port(self) -> int:
        try:
            return int(os.environ.get("FLASK_PORT", "5000"))
        except ValueError:
            logger.warning(
                "Invalid FLASK_PORT value '%s'; defaulting to 5000",
                os.environ.get("FLASK_PORT"),
            )
            return 5000

    @property
    def flask_debug(self) -> bool:
        return os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def validate_required(self, *names: str) -> list[str]:
        """
        Check that every listed variable name is present and non-empty.

        Returns a list of the missing variable names (empty list = all OK).

        This is a utility helper for components that want to validate a set of
        variables up-front (e.g., at application start-up) rather than waiting
        for a ``RuntimeError`` when a property is first accessed.  Call it from
        your entry point::

            missing = config.validate_required("TELEGRAM_BOT_TOKEN", "APPOINTMENT_QUEUE_URL")
            if missing:
                sys.exit(1)
        """
        missing = [n for n in names if not os.environ.get(n)]
        if missing:
            logger.error(
                "Missing required environment variable(s): %s. "
                "Check your .env file or process environment.",
                ", ".join(missing),
            )
        return missing


# Module-level singleton – import and use directly:
#   from app.config import config
config = Config()
