"""
Lambda entry point for all functions.
Routes events to the correct handler based on the event source.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def _is_api_gateway_event(event: dict) -> bool:
    return "httpMethod" in event or "requestContext" in event


def _is_sqs_event(event: dict) -> bool:
    records = event.get("Records", [])
    return bool(records) and records[0].get("eventSource") == "aws:sqs"


def _is_eventbridge_event(event: dict) -> bool:
    return event.get("source") == "aws.events" or "detail-type" in event


def handler(event: dict, context: object) -> dict:
    """
    Unified Lambda handler.
    Inspects the event shape and delegates to the appropriate function handler.
    """
    logger.info("lambda_handler invoked; routing event")

    if _is_api_gateway_event(event):
        logger.info("Routing to user_registration handler (API Gateway)")
        from app.lambda_functions.user_registration import handler as user_registration_handler
        return user_registration_handler(event, context)

    if _is_sqs_event(event):
        logger.info("Routing to send_notifications handler (SQS)")
        from app.lambda_functions.send_notifications import handler as send_notifications_handler
        return send_notifications_handler(event, context)

    if _is_eventbridge_event(event):
        logger.info("Routing to check_available_dates handler (EventBridge)")
        from app.lambda_functions.check_available_dates import handler as check_available_dates_handler
        return check_available_dates_handler(event, context)

    logger.warning("Unknown event source; event keys: %s", list(event.keys()))
    return {"statusCode": 400, "body": "Unknown event source"}
