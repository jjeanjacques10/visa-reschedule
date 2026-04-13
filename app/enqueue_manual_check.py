"""Enqueue a manual appointment-date check for a user.

This command sends a message to the configured SQS queue so the normal
`send_notifications` handler processes it. It is intended for local testing
with LocalStack but also works against AWS if your queue URL points to AWS.

Usage (repo root):
    python -m app.enqueue_manual_check --user-id <uuid>
    python -m app.enqueue_manual_check --telegram-id <id>

You can also run it as a script:
    python app/enqueue_manual_check.py --user-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import boto3

if __package__ in (None, ""):
    # Allow running as a script: `python app/enqueue_manual_check.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config, load_config
from app.database.dynamodb_client import DynamoDBClient
from app.utils.notification_utils import NotificationUtils


load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _sqs_endpoint_from_queue_url(queue_url: str) -> str | None:
    parsed = urlparse(queue_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enqueue a manual SQS check for a user and notify on completion."
    )
    ident = parser.add_mutually_exclusive_group(required=True)
    ident.add_argument("--user-id", help="User UUID (user_id) stored in DynamoDB")
    ident.add_argument("--telegram-id", help="Telegram ID stored in DynamoDB")

    parser.add_argument(
        "--notify-start",
        action="store_true",
        help="Send a Telegram message immediately saying the search started",
    )
    parser.add_argument(
        "--no-notify-complete",
        action="store_true",
        help="Do not notify when the search completes (default is to notify)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    missing = config.validate_required("APPOINTMENT_QUEUE_URL")
    if missing:
        raise SystemExit(2)

    db = DynamoDBClient()
    if args.user_id:
        user = db.get_user(args.user_id)
    else:
        user = db.get_user_by_telegram_id(str(args.telegram_id))

    if user is None:
        raise SystemExit("User not found in DynamoDB")

    try:
        bot_token = config.telegram_bot_token
    except RuntimeError:
        bot_token = ""
    notifier = NotificationUtils(bot_token=bot_token)

    if args.notify_start:
        notifier.send_message(
            chat_id=user.telegram_id,
            message=(
                "🔎 Iniciando busca manual por datas anteriores...\n"
                f"Agendamento atual: <b>{user.appointment_date}</b>"
            ),
        )

    queue_url = config.appointment_queue_url
    endpoint_url = _sqs_endpoint_from_queue_url(queue_url)
    sqs = boto3.client(
        "sqs",
        region_name=config.aws_region,
        endpoint_url=endpoint_url,
    )

    body = {
        "user_id": user.user_id,
        "manual": True,
        "notify_on_complete": not args.no_notify_complete,
        "requested_at": datetime.now(tz=timezone.utc).isoformat(),
        "request_source": "cli",
    }

    resp = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(body),
    )

    logger.info(
        "Manual check enqueued: user_id=%s messageId=%s",
        user.user_id,
        resp.get("MessageId"),
    )


if __name__ == "__main__":
    main()
