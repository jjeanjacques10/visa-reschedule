"""
Data models for the Visa Reschedule application.
Provides User and Appointment dataclasses with DynamoDB serialization helpers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class User:
    """Represents a registered user monitoring visa appointments."""

    user_id: str
    telegram_id: str
    visa_type: str
    appointment_date: str
    email: str
    password: str
    created_at: str = ""
    updated_at: str = ""
    notification_count: int = 0
    status: str = "pending"  # pending | notified | rescheduled | cancelled
    last_notified_date: Optional[str] = None
    preferred_dates: Optional[List[str]] = None
    payment_status: Optional[str] = None  # stub for future payment feature

    def to_dict(self) -> dict:
        """Serialize to a DynamoDB-compatible dictionary."""
        data = {
            "user_id": self.user_id,
            "telegram_id": self.telegram_id,
            "visa_type": self.visa_type,
            "appointment_date": self.appointment_date,
            "email": self.email,
            "password": self.password,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notification_count": self.notification_count,
            "status": self.status,
        }
        if self.last_notified_date is not None:
            data["last_notified_date"] = self.last_notified_date
        if self.preferred_dates is not None:
            data["preferred_dates"] = self.preferred_dates
        if self.payment_status is not None:
            data["payment_status"] = self.payment_status
        return data

    def to_safe_dict(self) -> dict:
        """Serialize without sensitive fields (password) for logging/responses."""
        data = self.to_dict()
        data.pop("password", None)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Deserialize from a DynamoDB item dictionary."""
        return cls(
            user_id=data["user_id"],
            telegram_id=data["telegram_id"],
            visa_type=data["visa_type"],
            appointment_date=data["appointment_date"],
            email=data["email"],
            password=data.get("password", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            notification_count=int(data.get("notification_count", 0)),
            status=data.get("status", "pending"),
            last_notified_date=data.get("last_notified_date"),
            preferred_dates=data.get("preferred_dates"),
            payment_status=data.get("payment_status"),
        )

    def __repr__(self) -> str:
        return (
            f"User(user_id={self.user_id!r}, telegram_id={self.telegram_id!r}, "
            f"visa_type={self.visa_type!r}, status={self.status!r})"
        )


@dataclass
class Appointment:
    """Represents a visa appointment slot snapshot from the scheduling website."""

    appointment_id: str
    visa_type: str
    available_dates: List[str] = field(default_factory=list)
    last_checked: str = ""

    def to_dict(self) -> dict:
        """Serialize to a DynamoDB-compatible dictionary."""
        return {
            "appointment_id": self.appointment_id,
            "visa_type": self.visa_type,
            "available_dates": self.available_dates,
            "last_checked": self.last_checked,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Appointment":
        """Deserialize from a DynamoDB item dictionary."""
        return cls(
            appointment_id=data["appointment_id"],
            visa_type=data["visa_type"],
            available_dates=data.get("available_dates", []),
            last_checked=data.get("last_checked", ""),
        )

    def __repr__(self) -> str:
        return (
            f"Appointment(appointment_id={self.appointment_id!r}, "
            f"visa_type={self.visa_type!r}, "
            f"available_dates_count={len(self.available_dates)})"
        )
