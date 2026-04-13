"""Local SQS worker for end-to-end testing.

This script polls the configured SQS queue (typically LocalStack) and invokes
the same handler that would run in AWS Lambda (app.lambda_functions.send_notifications).

Run from repo root:
  python -m app.local_sqs_worker
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3

if __package__ in (None, ""):
    # Allow running as a script: `python app/local_sqs_worker.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config, load_config

load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _sqs_endpoint_from_queue_url(queue_url: str) -> str | None:
    """Derive an SQS endpoint URL from a QueueUrl.

    This makes local usage robust even if boto3 would otherwise target real AWS.
    """
    parsed = urlparse(queue_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _get_int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %d", name, value, default)
        return default


def _build_lambda_sqs_event(messages: list[dict[str, Any]]) -> dict[str, Any]:
    records = []
    for msg in messages:
        records.append(
            {
                "messageId": msg.get("MessageId"),
                "receiptHandle": msg.get("ReceiptHandle"),
                "body": msg.get("Body"),
                "attributes": msg.get("Attributes", {}),
                "messageAttributes": msg.get("MessageAttributes", {}),
                "md5OfBody": msg.get("MD5OfBody"),
                "eventSource": "aws:sqs",
                "eventSourceARN": "localstack:sqs",
                "awsRegion": config.aws_region,
            }
        )
    return {"Records": records}


def run_forever() -> None:
    queue_url = config.appointment_queue_url
    endpoint_url = _sqs_endpoint_from_queue_url(queue_url)
    logger.info("Starting SQS worker: queue_url=%s endpoint_url=%s", queue_url, endpoint_url)

    sqs = boto3.client(
        "sqs",
        region_name=config.aws_region,
        endpoint_url=endpoint_url,
    )

    wait_time = _get_int_env("SQS_WAIT_TIME_SECONDS", 10)
    max_number = _get_int_env("SQS_MAX_NUMBER_OF_MESSAGES", 10)
    visibility_timeout = os.environ.get("SQS_VISIBILITY_TIMEOUT")
    poll_sleep = float(os.environ.get("SQS_POLL_SLEEP_SECONDS", "0.5"))

    from app.lambda_functions.send_notifications import handler as send_notifications_handler

    while True:
        params: dict[str, Any] = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": max_number,
            "WaitTimeSeconds": wait_time,
            "MessageAttributeNames": ["All"],
            "AttributeNames": ["All"],
        }
        if visibility_timeout:
            try:
                params["VisibilityTimeout"] = int(visibility_timeout)
            except ValueError:
                logger.warning("Invalid SQS_VISIBILITY_TIMEOUT=%r; ignoring", visibility_timeout)

        resp = sqs.receive_message(**params)
        messages = resp.get("Messages", [])
        if not messages:
            time.sleep(poll_sleep)
            continue

        logger.info("Received %d message(s)", len(messages))
        event = _build_lambda_sqs_event(messages)
        result = send_notifications_handler(event, None) or {}
        failures = {item.get("itemIdentifier") for item in result.get("batchItemFailures", [])}

        # Delete all successful messages (those not listed as failures).
        for msg in messages:
            message_id = msg.get("MessageId")
            if message_id and message_id in failures:
                logger.warning("Keeping failed message for retry: messageId=%s", message_id)
                continue
            try:
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Failed to delete messageId=%s: %s", message_id, exc)


def main() -> None:
    missing = config.validate_required("APPOINTMENT_QUEUE_URL")
    if missing:
        raise SystemExit(2)
    run_forever()


if __name__ == "__main__":
    main()
