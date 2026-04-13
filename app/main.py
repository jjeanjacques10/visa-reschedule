"""
Flask application for local testing of the Visa Reschedule service.
Mirrors the Lambda API Gateway surface so you can test without deploying.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, request

from app.config import config, load_config

# Load .env before anything else so all sub-modules see the variables.
load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def _get_db():
    from app.database.dynamodb_client import DynamoDBClient
    return DynamoDBClient()


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/register", methods=["POST"])
def register():
    """Register a new user. Mirrors Lambda user_registration handler."""
    from app.lambda_functions.user_registration import handler as reg_handler

    raw_body = request.get_data(as_text=True)
    fake_event = {"body": raw_body, "httpMethod": "POST"}
    result = reg_handler(fake_event, None)
    body = json.loads(result.get("body", "{}"))
    return jsonify(body), result.get("statusCode", 200)


@app.route("/users", methods=["GET"])
def list_users():
    """Return all active users (passwords masked)."""
    try:
        db = _get_db()
        users = db.list_active_users()
        return jsonify({"users": [u.to_safe_dict() for u in users]}), 200
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to list users: %s", exc)
        return jsonify({"error": "Failed to retrieve users"}), 500


@app.route("/check-dates", methods=["POST"])
def check_dates():
    """Manually trigger a date check for a specific user."""
    from app.utils.selenium_utils import SeleniumUtils
    from app.utils.notification_utils import NotificationUtils

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        db = _get_db()
        user = db.get_user(user_id)
        if user is None:
            return jsonify({"error": "User not found"}), 404

        selenium = SeleniumUtils(headless=config.selenium_headless)
        try:
            available_dates = selenium.check_dates_for_user(
                user_id=user.user_id,
                email=user.email,
                password=user.password,
                appointment_date=user.appointment_date,
            )
        finally:
            selenium.close()

        try:
            bot_token = config.telegram_bot_token
            if available_dates:
                notifier = NotificationUtils(bot_token=bot_token)
                notifier.send_available_dates_notification(
                    chat_id=user.telegram_id,
                    available_dates=available_dates,
                    current_date=user.appointment_date,
                )
        except RuntimeError as exc:
            logger.warning("Telegram notification skipped: %s", exc)

        return jsonify({"available_dates": available_dates}), 200
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Error during date check: %s", exc)
        return jsonify({"error": "Date check failed"}), 500


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    port = config.flask_port
    debug = config.flask_debug
    logger.info("Starting Flask app on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
