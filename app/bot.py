"""
Telegram polling bot entrypoint.
Delegates update processing to app.controller.bot_handler.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import urllib3

from app.config import load_config
from app.controller.bot_handler import BOT_TOKEN, process_telegram_update, telegram_api

load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

http = urllib3.PoolManager()


class TelegramBot:
    """Simple Telegram bot with long polling."""

    def __init__(self, token: str | None = None):
        self.token = token or BOT_TOKEN
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured.")
        self.offset = 0
        self.timeout = 30
        self.http = http

    def get_updates(self) -> list[dict]:
        """Fetch new Telegram updates."""
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        try:
            response = self.http.request(
                "GET",
                url,
                fields={"offset": self.offset, "timeout": self.timeout},
                timeout=self.timeout + 5,
            )
            data = json.loads(response.data.decode("utf-8"))
            if not data.get("ok"):
                logger.error("Failed to get updates: %s", data)
                return []
            updates = data.get("result", [])
            if updates:
                self.offset = updates[-1]["update_id"] + 1
            return updates
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Error fetching updates: %s", exc)
            return []

    def handle_update(self, update: dict) -> None:
        """Process one Telegram update."""
        try:
            process_telegram_update(update)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "Error processing update_id=%s: %s",
                update.get("update_id"),
                exc,
            )

    def send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown"):
        """Send a direct Telegram message."""
        try:
            return telegram_api(
                "sendMessage",
                {"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Error sending message: %s", exc)
            return None

    def run(self) -> None:
        """Main polling loop."""
        logger.info("Telegram bot started.")
        while True:
            updates = self.get_updates()
            for update in updates:
                self.handle_update(update)
            if not updates:
                time.sleep(1)


def main() -> None:
    bot = TelegramBot()
    bot.run()


if __name__ == "__main__":
    main()
