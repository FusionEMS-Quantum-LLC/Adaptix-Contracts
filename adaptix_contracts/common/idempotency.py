"""Idempotency contracts for Adaptix services."""

from datetime import datetime
from pydantic import BaseModel


class IdempotencyRecord(BaseModel):
    idempotency_key: str
    tenant_id: str
    service: str
    operation: str
    request_hash: str
    response_status: int
    response_body: dict | None = None
    created_at: datetime
    expires_at: datetime | None = None
    is_duplicate: bool = False
