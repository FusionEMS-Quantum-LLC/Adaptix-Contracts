"""Stripe subscription-payment contracts shared across Adaptix services.

Canonical Stripe customer/subscription/invoice references, checkout and
customer-portal session request/response envelopes, and payment events for the
AdaptixCore Payment shared service.

This module covers platform SaaS subscription billing via Stripe and is
distinct from ambulance-claim billing (``billing_contracts``). Monetary
amounts are represented as ``Decimal`` in major currency units; when bridging
to the Stripe API (which uses integer minor units) convert accordingly.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubscriptionStatus(str, Enum):
    """Stripe subscription lifecycle status."""

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"


class InvoiceStatus(str, Enum):
    """Stripe invoice status."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    UNCOLLECTIBLE = "uncollectible"
    VOID = "void"


class PaymentEventType(str, Enum):
    """Payment lifecycle event types."""

    CHECKOUT_COMPLETED = "checkout.completed"
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_DELETED = "subscription.deleted"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    REFUNDED = "refunded"


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------


class StripeCustomerRef(BaseModel):
    """Link between a tenant and its Stripe customer."""

    tenant_id: UUID
    stripe_customer_id: str = Field(..., min_length=1, max_length=64)
    email: Optional[str] = Field(None, max_length=320)
    default_payment_method_id: Optional[str] = Field(None, max_length=64)
    created_at: Optional[datetime] = None


class SubscriptionRef(BaseModel):
    """Reference to a tenant's Stripe subscription."""

    tenant_id: UUID
    stripe_subscription_id: str = Field(..., min_length=1, max_length=64)
    stripe_customer_id: str = Field(..., min_length=1, max_length=64)
    status: SubscriptionStatus
    price_id: Optional[str] = Field(None, max_length=64)
    product_id: Optional[str] = Field(None, max_length=64)
    quantity: int = Field(1, ge=0)
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    trial_end: Optional[datetime] = None


class InvoiceRef(BaseModel):
    """Reference to a Stripe invoice."""

    tenant_id: UUID
    stripe_invoice_id: str = Field(..., min_length=1, max_length=64)
    stripe_customer_id: str = Field(..., min_length=1, max_length=64)
    stripe_subscription_id: Optional[str] = Field(None, max_length=64)
    status: InvoiceStatus
    amount_due: Decimal = Field(..., ge=Decimal("0"))
    amount_paid: Decimal = Field(Decimal("0"), ge=Decimal("0"))
    currency: str = Field("usd", min_length=3, max_length=3)
    hosted_invoice_url: Optional[str] = None
    invoice_pdf_url: Optional[str] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Checkout & Portal Sessions
# ---------------------------------------------------------------------------


class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe Checkout session for a subscription."""

    tenant_id: UUID
    correlation_id: Optional[str] = None
    price_id: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(1, ge=1)
    success_url: str = Field(..., min_length=1, max_length=2000)
    cancel_url: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field("subscription", max_length=32)
    customer_email: Optional[str] = Field(None, max_length=320)
    stripe_customer_id: Optional[str] = Field(None, max_length=64)
    metadata: dict[str, str] = Field(default_factory=dict)


class CheckoutSessionResponse(BaseModel):
    """Response returning the hosted Stripe Checkout URL."""

    tenant_id: UUID
    session_id: str = Field(..., min_length=1, max_length=200)
    checkout_url: str = Field(..., min_length=1, max_length=2000)
    correlation_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class PortalSessionRequest(BaseModel):
    """Request to create a Stripe customer-portal session."""

    tenant_id: UUID
    correlation_id: Optional[str] = None
    stripe_customer_id: str = Field(..., min_length=1, max_length=64)
    return_url: str = Field(..., min_length=1, max_length=2000)


class PortalSessionResponse(BaseModel):
    """Response returning the hosted Stripe customer-portal URL."""

    tenant_id: UUID
    portal_url: str = Field(..., min_length=1, max_length=2000)
    correlation_id: Optional[str] = None
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class PaymentEvent(BaseModel):
    """A payment lifecycle event derived from a Stripe webhook."""

    event_id: Optional[UUID] = None
    tenant_id: UUID
    event_type: PaymentEventType
    stripe_event_id: Optional[str] = Field(None, max_length=64)
    stripe_customer_id: Optional[str] = Field(None, max_length=64)
    stripe_subscription_id: Optional[str] = Field(None, max_length=64)
    stripe_invoice_id: Optional[str] = Field(None, max_length=64)
    amount: Optional[Decimal] = Field(None, ge=Decimal("0"))
    currency: str = Field("usd", min_length=3, max_length=3)
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
