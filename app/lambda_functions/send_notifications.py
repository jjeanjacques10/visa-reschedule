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

from app.database.dynamodb_client import DynamoDBClient
from app.utils.notification_utils import NotificationUtils
from app.utils.selenium_utils import SeleniumUtils

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_db_client: DynamoDBClient | None = None


def _get_db_client() -> DynamoDBClient:
    global _db_client
    if _db_client is None:
        _db_client = DynamoDBClient()
    return _db_client


def _get_notification_utils() -> NotificationUtils:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN is not set; notifications will fail")
    return NotificationUtils(bot_token=bot_token)


def _process_record(record: dict, db: DynamoDBClient, notifier: NotificationUtils) -> None:
    """Process a single SQS record: check dates and notify if applicable."""
    try:
        body = json.loads(record["body"])
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("Failed to parse SQS record body: %s", exc)
        return

    user_id = body.get("user_id")
    if not user_id:
        logger.error("SQS record missing user_id: %s", body)
        return

    # Always fetch fresh user data from DynamoDB (SQS message may be stale)
    user = db.get_user(user_id)
    if user is None:
        logger.warning("User not found in DynamoDB: user_id=%s", user_id)
        return

    if user.status == "cancelled":
        logger.info("Skipping cancelled user: user_id=%s", user_id)
        return

    logger.info(
        "Checking dates for user_id=%s appointment_date=%s",
        user_id,
        user.appointment_date,
    )

    selenium = SeleniumUtils(headless=True)
    try:
        available_dates = selenium.check_dates_for_user(user.to_dict())
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            "Selenium check failed for user_id=%s: %s", user_id, exc
        )
        return
    finally:
        selenium.close()

    if not available_dates:
        logger.info("No earlier dates found for user_id=%s", user_id)
        return

    logger.info(
        "Found %d earlier date(s) for user_id=%s: %s",
        len(available_dates),
        user_id,
        available_dates,
    )

    # Send Telegram notification
    sent = notifier.send_available_dates_notification(
        chat_id=user.telegram_id,
        available_dates=available_dates,
        current_date=user.appointment_date,
    )

    if sent:
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        db.update_user(
            user_id,
            {
                "last_notified_date": now_iso,
                "notification_count": user.notification_count + 1,
                "status": "notified",
            },
        )
        logger.info("Notification sent and user updated: user_id=%s", user_id)
    else:
        logger.warning("Notification failed for user_id=%s", user_id)


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
