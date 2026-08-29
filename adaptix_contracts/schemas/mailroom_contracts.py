"""Physical mail (mailroom) contracts shared across Adaptix services.

Canonical mail packet, sender/recipient, delivery/return status, and status
enums for the AdaptixCore Mailroom shared service. Physical mail is delivered
exclusively via PostGrid; no other print/mail provider types are defined here.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MailStatus(str, Enum):
    """Lifecycle state of a mail packet."""

    DRAFT = "draft"
    QUEUED = "queued"
    SUBMITTED_TO_POSTGRID = "submitted_to_postgrid"
    ACCEPTED = "accepted"
    PRINTING = "printing"
    MAILED = "mailed"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    RETURNED = "returned"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_REVIEW = "requires_review"


class MailClass(str, Enum):
    """PostGrid mail class."""

    FIRST_CLASS = "first_class"
    STANDARD_CLASS = "standard_class"
    CERTIFIED = "certified"
    CERTIFIED_RETURN_RECEIPT = "certified_return_receipt"
    EXPRESS = "express"


class MailReturnReason(str, Enum):
    """Reason a mail piece was returned to sender."""

    UNDELIVERABLE = "undeliverable"
    REFUSED = "refused"
    VACANT = "vacant"
    NO_SUCH_NUMBER = "no_such_number"
    INSUFFICIENT_ADDRESS = "insufficient_address"
    MOVED_NO_FORWARDING = "moved_no_forwarding"
    DECEASED = "deceased"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------


class MailRecipient(BaseModel):
    """Destination address for a mail packet."""

    name: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    address_line1: str = Field(..., min_length=1, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: str = Field(..., min_length=1, max_length=120)
    state: str = Field(..., min_length=2, max_length=2)
    postal_code: str = Field(..., min_length=1, max_length=16)
    country: str = Field(default="US", min_length=2, max_length=2)


class MailSender(BaseModel):
    """Return address for a mail packet."""

    name: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    address_line1: str = Field(..., min_length=1, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: str = Field(..., min_length=1, max_length=120)
    state: str = Field(..., min_length=2, max_length=2)
    postal_code: str = Field(..., min_length=1, max_length=16)
    country: str = Field(default="US", min_length=2, max_length=2)


# ---------------------------------------------------------------------------
# Packet & Status
# ---------------------------------------------------------------------------


class MailPacket(BaseModel):
    """A physical mail piece to be printed and mailed via PostGrid."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    correlation_id: Optional[str] = None
    sender: MailSender
    recipient: MailRecipient
    mail_class: MailClass = MailClass.FIRST_CLASS
    status: MailStatus = MailStatus.DRAFT
    template_id: Optional[str] = Field(default=None, max_length=160)
    document_url: Optional[str] = Field(default=None, max_length=2000)
    description: Optional[str] = Field(default=None, max_length=1000)
    page_count: Optional[int] = Field(default=None, ge=1)
    color: bool = False
    double_sided: bool = True
    postgrid_id: Optional[str] = Field(default=None, max_length=128)
    reference_type: Optional[str] = Field(default=None, max_length=120)
    reference_id: Optional[str] = Field(default=None, max_length=255)
    created_at: datetime
    updated_at: datetime


class MailDeliveryStatus(BaseModel):
    """Delivery tracking state for a mail packet."""

    model_config = ConfigDict(from_attributes=True)

    packet_id: UUID
    tenant_id: UUID
    status: MailStatus
    postgrid_id: Optional[str] = Field(default=None, max_length=128)
    tracking_number: Optional[str] = Field(default=None, max_length=128)
    mailed_at: Optional[datetime] = None
    expected_delivery_date: Optional[date] = None
    delivered_at: Optional[datetime] = None
    updated_at: datetime


class MailReturnStatus(BaseModel):
    """Return-to-sender state for a mail packet."""

    model_config = ConfigDict(from_attributes=True)

    packet_id: UUID
    tenant_id: UUID
    returned: bool = True
    reason: MailReturnReason
    postgrid_id: Optional[str] = Field(default=None, max_length=128)
    returned_at: Optional[datetime] = None
    requires_review: bool = True
    notes: Optional[str] = Field(default=None, max_length=1000)
