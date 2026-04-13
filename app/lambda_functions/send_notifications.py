"""
Lambda function – Send Notifications.
Triggered by SQS. For each record, uses Selenium to check available visa
appointment dates and sends a Telegram notification if earlier dates exist.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from app.config import load_config
from app.database.dynamodb_client import DynamoDBClient
from app.utils.notification_utils import NotificationUtils
from app.utils.selenium_utils import SeleniumUtils

# Load .env when running locally (SAM CLI / unit tests); no-op in real Lambda.
load_config()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_db_client: DynamoDBClient | None = None


def _get_db_client() -> DynamoDBClient:
    global _db_client
    if _db_client is None:
        _db_client = DynamoDBClient()
    return _db_client


def _get_notification_utils() -> NotificationUtils:
    try:
        from app.config import config
        bot_token = config.telegram_bot_token
    except RuntimeError:
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not set; notifications will not be sent. "
            "Add it to your .env file or process environment."
        )
        bot_token = ""
    return NotificationUtils(bot_token=bot_token)


def _resolve_user_from_record(body: dict, db: DynamoDBClient):
    """Resolve a user from SQS body using user_id first, then telegram_id."""
    user_id = body.get("user_id")
    telegram_id = body.get("telegram_id")

    if user_id:
        user = db.get_user(str(user_id))
        if user is not None:
            return user

    if telegram_id:
        user = db.get_user_by_telegram_id(str(telegram_id))
        if user is not None:
            return user

    return None


def _now_utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _already_notified_today_utc(last_notified_date: str | None) -> bool:
    """Return True when last notification date is on the current UTC day."""
    if not last_notified_date:
        return False

    try:
        parsed = datetime.fromisoformat(last_notified_date.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Invalid last_notified_date format: %s", last_notified_date)
        return False

    return parsed.astimezone(timezone.utc).date() == datetime.now(tz=timezone.utc).date()


def _can_send_daily_notification(user) -> bool:
    return not _already_notified_today_utc(user.last_notified_date)


def _process_record(record: dict, db: DynamoDBClient, notifier: NotificationUtils) -> None:
    """Process a single SQS record: check dates and notify if applicable."""
    try:
        body = json.loads(record["body"])
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("Failed to parse SQS record body: %s", exc)
        return

    notify_on_complete = bool(body.get("notify_on_complete", True))

    # Always fetch fresh user data from DynamoDB (SQS message may be stale)
    user = _resolve_user_from_record(body, db)
    if user is None:
        logger.warning(
            "User not found in DynamoDB for record identifiers user_id=%s telegram_id=%s",
            body.get("user_id"),
            body.get("telegram_id"),
        )
        return

    if user.status == "cancelled":
        logger.info("Skipping cancelled user: user_id=%s", user.user_id)
        return

    logger.info("Checking dates for user_id=%s", user.user_id)

    selenium = SeleniumUtils(headless=True)
    try:
        available_dates = selenium.check_dates_for_user(
            user_id=user.user_id,
            email=user.email,
            password=user.password,
            appointment_date=user.appointment_date,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Selenium check failed for user_id=%s: %s", user.user_id, exc
        )
        if notify_on_complete:
            notifier.send_message(
                chat_id=user.telegram_id,
                message=(
                    "❌ <b>Busca concluída com erro.</b>\n"
                    "Tente novamente em alguns minutos."
                ),
            )
        return
    finally:
        selenium.close()

    if not available_dates:
        logger.info("No earlier dates found for user_id=%s", user.user_id)
        if not notify_on_complete:
            return
        if not _can_send_daily_notification(user):
            logger.info(
                "Skipping no-dates notification for user_id=%s: already notified today",
                user.user_id,
            )
            return
        sent = notifier.send_message(
            chat_id=user.telegram_id,
            message=(
                "✅ <b>Busca concluída.</b>\n"
                "Nenhuma data anterior foi encontrada no momento.\n"
                f"Agendamento atual: <b>{user.appointment_date}</b>"
            ),
        )
        if sent:
            db.update_user(
                user.user_id,
                {
                    "last_notified_date": _now_utc_iso(),
                    "notification_count": user.notification_count + 1,
                    "status": "pending",
                },
            )
        return

    logger.info(
        "Found %d earlier date(s) for user_id=%s: %s",
        len(available_dates),
        user.user_id,
        available_dates,
    )

    if not _can_send_daily_notification(user):
        logger.info(
            "Skipping available-dates notification for user_id=%s: already notified today",
            user.user_id,
        )
        return

    # Send Telegram notification
    sent = notifier.send_available_dates_notification(
        chat_id=user.telegram_id,
        available_dates=available_dates,
        current_date=user.appointment_date,
    )

    if sent:
        db.update_user(
            user.user_id,
            {
                "last_notified_date": _now_utc_iso(),
                "notification_count": user.notification_count + 1,
                "status": "notified",
            },
        )
        logger.info("Notification sent and user updated: user_id=%s", user.user_id)
    else:
        logger.warning("Notification failed for user_id=%s", user.user_id)


def handler(event: dict, context: object) -> dict:
    """Process all SQS records in the batch."""
    records = event.get("Records", [])
    logger.info("send_notifications handler invoked with %d record(s)", len(records))

    db = _get_db_client()
    notifier = _get_notification_utils()

    success_count = 0
    failure_count = 0
    failed_message_ids = []

    for record in records:
        message_id = record.get("messageId", "unknown")
        try:
            _process_record(record, db, notifier)
            success_count += 1
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "Unhandled error processing messageId=%s: %s", message_id, exc
            )
            failure_count += 1
            failed_message_ids.append(message_id)

    logger.info(
        "send_notifications complete: success=%d failure=%d",
        success_count,
        failure_count,
    )

    # Return failed message IDs so SQS can retry them
    response: dict = {}
    if failed_message_ids:
        response["batchItemFailures"] = [
            {"itemIdentifier": mid} for mid in failed_message_ids
        ]
    return response
