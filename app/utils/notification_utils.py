"""
Telegram notification utilities.
Sends messages to users via the Telegram Bot API.
"""

from __future__ import annotations

import logging
from typing import List

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class NotificationUtils:
    """Sends Telegram notifications using the Bot API via HTTP."""

    def __init__(self, bot_token: str) -> None:
        if not bot_token:
            logger.warning("NotificationUtils initialised without a bot token")
        self.bot_token = bot_token
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    def send_message(self, chat_id: str, message: str) -> bool:
        """
        Send a plain-text message to a Telegram chat.

        Returns True on success, False on failure.
        """
        if not self.bot_token:
            logger.error("Cannot send Telegram message: bot_token is not set")
            return False

        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                logger.info(
                    "Telegram message sent successfully to chat_id=%s", chat_id
                )
                return True
            logger.error(
                "Telegram API returned ok=false for chat_id=%s: %s",
                chat_id,
                data,
            )
            return False
        except requests.exceptions.Timeout:
            logger.error(
                "Telegram API request timed out for chat_id=%s", chat_id
            )
            return False
        except requests.exceptions.HTTPError as exc:
            logger.error(
                "Telegram API HTTP error for chat_id=%s: %s", chat_id, exc
            )
            return False
        except requests.exceptions.RequestException as exc:
            logger.exception(
                "Unexpected error sending Telegram message to chat_id=%s: %s",
                chat_id,
                exc,
            )
            return False

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def format_dates_message(
        self, available_dates: List[str], current_date: str
    ) -> str:
        """Format a human-readable notification message in Brazilian Portuguese."""
        dates_list = "\n".join(f"  • {d}" for d in sorted(available_dates))
        return (
            "🗓️ <b>Datas disponíveis para reagendamento!</b>\n\n"
            f"Seu agendamento atual: <b>{current_date}</b>\n\n"
            "Datas disponíveis (anteriores ao seu agendamento atual):\n"
            f"{dates_list}\n\n"
            "Acesse <a href='https://ais.usvisa-info.com/pt-br/niv'>o portal</a> "
            "para reagendar sua entrevista."
        )

    def send_available_dates_notification(
        self,
        chat_id: str,
        available_dates: List[str],
        current_date: str,
    ) -> bool:
        """
        Send a formatted notification about available earlier appointment dates.

        Returns True on success, False on failure.
        """
        if not available_dates:
            logger.debug(
                "No available dates to notify for chat_id=%s", chat_id
            )
            return False

        message = self.format_dates_message(available_dates, current_date)
        logger.info(
            "Sending available-dates notification to chat_id=%s "
            "(%d date(s) available)",
            chat_id,
            len(available_dates),
        )
        return self.send_message(chat_id, message)
