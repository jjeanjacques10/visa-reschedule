"""
Lambda function – User Registration.
Triggered by API Gateway POST /register.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from app.config import load_config
from app.database.dynamodb_client import DynamoDBClient
from app.database.models import User

# Load .env when running locally (SAM CLI / unit tests); no-op in real Lambda.
load_config()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_db_client: DynamoDBClient | None = None

REQUIRED_FIELDS = ("email", "telegram_id", "visa_type", "appointment_date", "password")


def _get_db_client() -> DynamoDBClient:
    """Return a cached DynamoDB client (initialised once per Lambda container)."""
    global _db_client
    if _db_client is None:
        _db_client = DynamoDBClient()
    return _db_client


def _build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event: dict, context: object) -> dict:
    """Register a new user via API Gateway event."""
    logger.info("user_registration handler invoked")

    # Parse request body
    try:
        raw_body = event.get("body") or "{}"
        if isinstance(raw_body, str):
            body = json.loads(raw_body)
        else:
            body = raw_body
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Invalid JSON body: %s", exc)
        return _build_response(400, {"error": "Invalid JSON body"})

    # Validate required fields
    missing = [f for f in REQUIRED_FIELDS if not body.get(f)]
    if missing:
        logger.warning("Missing required fields: %s", missing)
        return _build_response(
            400, {"error": f"Missing required fields: {', '.join(missing)}"}
        )

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    user = User(
        user_id=str(uuid4()),
        telegram_id=str(body["telegram_id"]),
        visa_type=body["visa_type"],
        appointment_date=body["appointment_date"],
        email=body["email"],
        password=body["password"],
        created_at=now_iso,
        updated_at=now_iso,
        notification_count=0,
        status="pending",
        preferred_dates=body.get("preferred_dates"),
        payment_status=body.get("payment_status"),
    )

    try:
        db = _get_db_client()
        created_user = db.create_user(user)
        logger.info(
            "User registered successfully: user_id=%s telegram_id=%s",
            created_user.user_id,
            created_user.telegram_id,
        )
        # Never return the password in the response
        return _build_response(200, {"user": created_user.to_safe_dict()})
    except ValueError:
        logger.warning("User registration conflict: user already exists")
        return _build_response(409, {"error": "User already exists"})
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error during user registration: %s", exc)
        return _build_response(500, {"error": "Internal server error"})
