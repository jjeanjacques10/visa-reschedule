"""
DynamoDB client for the Visa Reschedule application.
Provides CRUD operations for User and Appointment entities.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.database.models import Appointment, User

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """Thin wrapper around boto3 DynamoDB resource for visa-reschedule entities."""

    def __init__(
        self,
        users_table_name: Optional[str] = None,
        appointments_table_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        users_telegram_index_name: Optional[str] = None,
    ) -> None:
        self.users_table_name = users_table_name or os.environ.get(
            "DYNAMODB_USERS_TABLE", "visa-reschedule-users"
        )
        self.appointments_table_name = appointments_table_name or os.environ.get(
            "DYNAMODB_APPOINTMENTS_TABLE", "visa-reschedule-appointments"
        )
        self.endpoint_url = endpoint_url or os.environ.get("DYNAMODB_ENDPOINT_URL")
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self.users_telegram_index_name = users_telegram_index_name or os.environ.get(
            "DYNAMODB_USERS_TELEGRAM_INDEX", "telegram_id-index"
        )

        kwargs: dict = {"region_name": self.region_name}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url

        self._dynamodb = boto3.resource("dynamodb", **kwargs)
        self._users_table = self._dynamodb.Table(self.users_table_name)
        self._appointments_table = self._dynamodb.Table(self.appointments_table_name)
        logger.info(
            "DynamoDBClient initialised: endpoint=%s, region=%s, users_table=%s, appointments_table=%s",
            self.endpoint_url or "AWS_DEFAULT_ENDPOINT",
            self.region_name,
            self.users_table_name,
            self.appointments_table_name,
        )

    # ------------------------------------------------------------------
    # User operations
    # ------------------------------------------------------------------

    def create_user(self, user: User) -> User:
        """Persist a new User item. Raises if the item already exists."""
        try:
            self._users_table.put_item(
                Item=user.to_dict(),
                ConditionExpression=Attr("user_id").not_exists(),
            )
            logger.info("Created user user_id=%s", user.user_id)
            return user
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code == "ConditionalCheckFailedException":
                logger.warning("User already exists: user_id=%s", user.user_id)
                raise ValueError(f"User {user.user_id} already exists") from exc
            logger.exception("Failed to create user user_id=%s", user.user_id)
            raise

    def get_user(self, user_id: str) -> Optional[User]:
        """Retrieve a User by primary key. Returns None if not found."""
        try:
            response = self._users_table.get_item(Key={"user_id": user_id})
            item = response.get("Item")
            if item is None:
                logger.debug("User not found: user_id=%s", user_id)
                return None
            return User.from_dict(item)
        except ClientError:
            logger.exception("Failed to get user user_id=%s", user_id)
            raise

    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        """Lookup a user by telegram_id using GSI (fallback to scan)."""
        try:
            response = self._users_table.query(
                IndexName=self.users_telegram_index_name,
                KeyConditionExpression=Key("telegram_id").eq(telegram_id),
                Limit=1,
            )
            items = response.get("Items", [])
            if not items:
                logger.debug("User not found: telegram_id=%s", telegram_id)
                return None
            return User.from_dict(items[0])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ValidationException":
                logger.warning(
                    "Users telegram_id index '%s' is unavailable; falling back to scan.",
                    self.users_telegram_index_name,
                )
                response = self._users_table.scan(
                    FilterExpression=Attr("telegram_id").eq(telegram_id)
                )
                items = response.get("Items", [])
                if not items:
                    logger.debug("User not found: telegram_id=%s", telegram_id)
                    return None
                return User.from_dict(items[0])
            logger.exception(
                "Failed to get user by telegram_id=%s", telegram_id
            )
            raise
    def update_user(self, user_id: str, updates: dict) -> User:
        """Apply a partial update to an existing User item."""
        updates["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        # Build UpdateExpression dynamically
        set_expressions = []
        expression_attribute_names: dict = {}
        expression_attribute_values: dict = {}

        for key, value in updates.items():
            placeholder = f"#attr_{key}"
            value_key = f":val_{key}"
            set_expressions.append(f"{placeholder} = {value_key}")
            expression_attribute_names[placeholder] = key
            expression_attribute_values[value_key] = value

        update_expression = "SET " + ", ".join(set_expressions)

        try:
            response = self._users_table.update_item(
                Key={"user_id": user_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW",
            )
            updated_item = response["Attributes"]
            logger.info("Updated user user_id=%s fields=%s", user_id, list(updates.keys()))
            return User.from_dict(updated_item)
        except ClientError:
            logger.exception("Failed to update user user_id=%s", user_id)
            raise

    def list_active_users(self) -> List[User]:
        """Return all users whose status is not 'cancelled'."""
        try:
            response = self._users_table.scan(
                FilterExpression=Attr("status").ne("cancelled")
            )
            items = response.get("Items", [])

            # Handle DynamoDB pagination
            while "LastEvaluatedKey" in response:
                response = self._users_table.scan(
                    FilterExpression=Attr("status").ne("cancelled"),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                items.extend(response.get("Items", []))

            users = [User.from_dict(item) for item in items]
            logger.info("Listed %d active users", len(users))
            return users
        except ClientError:
            logger.exception("Failed to list active users")
            raise

    def delete_user(self, user_id: str) -> None:
        """Delete a User item by primary key."""
        try:
            self._users_table.delete_item(Key={"user_id": user_id})
            logger.info("Deleted user user_id=%s", user_id)
        except ClientError:
            logger.exception("Failed to delete user user_id=%s", user_id)
            raise

    # ------------------------------------------------------------------
    # Appointment operations
    # ------------------------------------------------------------------

    def create_appointment(self, appointment: Appointment) -> Appointment:
        """Persist a new Appointment item."""
        try:
            self._appointments_table.put_item(Item=appointment.to_dict())
            logger.info(
                "Created appointment appointment_id=%s", appointment.appointment_id
            )
            return appointment
        except ClientError:
            logger.exception(
                "Failed to create appointment appointment_id=%s",
                appointment.appointment_id,
            )
            raise

    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        """Retrieve an Appointment by primary key. Returns None if not found."""
        try:
            response = self._appointments_table.get_item(
                Key={"appointment_id": appointment_id}
            )
            item = response.get("Item")
            if item is None:
                logger.debug(
                    "Appointment not found: appointment_id=%s", appointment_id
                )
                return None
            return Appointment.from_dict(item)
        except ClientError:
            logger.exception(
                "Failed to get appointment appointment_id=%s", appointment_id
            )
            raise

    def update_appointment(self, appointment_id: str, updates: dict) -> Appointment:
        """Apply a partial update to an existing Appointment item."""
        set_expressions = []
        expression_attribute_names: dict = {}
        expression_attribute_values: dict = {}

        for key, value in updates.items():
            placeholder = f"#attr_{key}"
            value_key = f":val_{key}"
            set_expressions.append(f"{placeholder} = {value_key}")
            expression_attribute_names[placeholder] = key
            expression_attribute_values[value_key] = value

        update_expression = "SET " + ", ".join(set_expressions)

        try:
            response = self._appointments_table.update_item(
                Key={"appointment_id": appointment_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW",
            )
            updated_item = response["Attributes"]
            logger.info(
                "Updated appointment appointment_id=%s fields=%s",
                appointment_id,
                list(updates.keys()),
            )
            return Appointment.from_dict(updated_item)
        except ClientError:
            logger.exception(
                "Failed to update appointment appointment_id=%s", appointment_id
            )
            raise
