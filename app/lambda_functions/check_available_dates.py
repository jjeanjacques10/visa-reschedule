"""
Lambda function – Check Available Dates.
Triggered by EventBridge/CloudWatch schedule (3× daily).
Fetches all active users and enqueues each one into SQS for processing.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

from app.config import load_config
from app.database.dynamodb_client import DynamoDBClient

# Load .env when running locally (SAM CLI / unit tests); no-op in real Lambda.
load_config()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_db_client: DynamoDBClient | None = None
_sqs_client = None


def _get_db_client() -> DynamoDBClient:
    global _db_client
    if _db_client is None:
        _db_client = DynamoDBClient()
    return _db_client


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _sqs_client


def _send_to_sqs(queue_url: str, safe_payload: dict) -> None:
    """Send a single user payload (no password) to the SQS queue."""
    message_body = json.dumps(safe_payload)
    try:
        _get_sqs_client().send_message(
            QueueUrl=queue_url,
            MessageBody=message_body,
        )
        logger.info("Enqueued user_id=%s to SQS", safe_payload.get("user_id"))
    except ClientError:
        logger.exception(
            "Failed to send SQS message for user_id=%s", safe_payload.get("user_id")
        )
        raise


def handler(event: dict, context: object) -> dict:
    """Collect active users and dispatch each to SQS for date-checking."""
    from app.config import config
    try:
        queue_url = config.appointment_queue_url
    except RuntimeError as exc:
        logger.error("%s", exc)
        return {"statusCode": 500, "body": "APPOINTMENT_QUEUE_URL not configured"}

    logger.info("check_available_dates handler invoked")

    db = _get_db_client()
    try:
        users = db.list_active_users()
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to list active users: %s", exc)
        return {"statusCode": 500, "body": "Failed to retrieve users"}

    logger.info("Processing %d active user(s)", len(users))

    enqueued = 0
    failed = 0
    for user in users:
        # Basic sanity check before enqueueing
        if not user.email or not user.password:
            logger.warning(
                "Skipping user_id=%s: missing credentials", user.user_id
            )
            continue
        try:
            payload = user.to_safe_dict()
            payload["notify_on_complete"] = True
            _send_to_sqs(queue_url, payload)
            enqueued += 1
        except ClientError:
            failed += 1
            # Continue processing remaining users even if one fails

    logger.info(
        "check_available_dates complete: enqueued=%d failed=%d", enqueued, failed
    )
    return {
        "statusCode": 200,
        "body": json.dumps({"enqueued": enqueued, "failed": failed}),
    }
