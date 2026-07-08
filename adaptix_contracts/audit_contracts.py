"""Adaptix platform audit service client contract.

.. deprecated:: 1.5.0
    This module is the legacy **direct-write** audit client: it embeds
    persistence in every caller (each domain service writes to its own
    ``audit_log_entries`` table via its own session, no network call). That
    architecture predates the standalone AdaptixCore Audit service and is
    superseded by the canonical service surface in
    :mod:`adaptix_contracts.schemas.audit_contracts`
    (``AuditEvent`` + ``AuditIngestRequest``/``AuditIngestResponse`` +
    ``AuditSearchQuery``/``AuditSearchResponse`` +
    ``AuditExportRequest``/``AuditExportResponse`` + the four ``audit.*``
    events). New services must emit through the Audit service, not this
    client.

    This module is retained for backward compatibility only — it is still
    imported by live consumers (Adaptix-CAD-Service ``cad_app/audit_service.py``
    and migration ``019_add_audit_log_entries``; Adaptix-Fire-Service
    ``fire_app/audit_service.py``). Per the deprecation policy the import path
    and behaviour are preserved and will be removed only in the next major
    version, after those consumers migrate to the Audit service. Do not add
    new callers.

Provides a canonical AuditServiceClient used by all domain services to
write structured, tenant-scoped audit records into the Core audit log
table. All domain-level mutations must record actor, tenant, prior/new
state through this client.

The client writes directly to the ``cad_audit_logs``-equivalent table via
the active SQLAlchemy async session. Each domain service passes its own
session; no cross-service network call is made.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class _AuditBase(DeclarativeBase):
    """Isolated declarative base for audit log model."""

    pass


class AuditLogEntry(_AuditBase):
    """Immutable audit log entry written by AuditServiceClient.

    This model is intentionally minimal — it captures the canonical fields
    required for compliance, tracing, and security review.

    Attributes:
        id: UUID primary key.
        tenant_id: Tenant context.
        actor_user_id: User performing the action (nullable for system events).
        action: Dot-namespaced action string e.g. ``cad.case.created``.
        resource_type: Entity type e.g. ``case``, ``unit``, ``assignment``.
        resource_id: Entity identifier string.
        changes_before: JSON snapshot of relevant fields before the mutation.
        changes_after: JSON snapshot of relevant fields after the mutation.
        created_at: UTC timestamp of the audit event.
    """

    __tablename__ = "audit_log_entries"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changes_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changes_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLogEntry {self.id} ({self.action} on {self.resource_type} "
            f"{self.resource_id} by {self.actor_user_id})>"
        )


class AuditServiceClient:
    """Canonical client for writing structured audit records.

    All domain services use this client to record mutations. The client
    writes directly to the ``audit_log_entries`` table via the caller's
    active async session. No network call is made.

    Usage::

        await AuditServiceClient.log_action(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action="cad.case.created",
            resource_type="case",
            resource_id=str(case.id),
            changes_after={"call_type": call_type},
            session=session,
        )
    """

    @staticmethod
    async def log_action(
        *,
        tenant_id: UUID,
        action: str,
        resource_type: str,
        session: AsyncSession,
        actor_user_id: UUID | None = None,
        resource_id: str | None = None,
        changes_before: dict[str, Any] | None = None,
        changes_after: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        **_ignored_kwargs: Any,
    ) -> AuditLogEntry:
        """Write a structured audit record for a domain mutation.

        Args:
            tenant_id: Tenant context UUID.
            action: Dot-namespaced action string (e.g. ``cad.case.created``).
            resource_type: Entity type string (e.g. ``case``, ``unit``).
            session: Active SQLAlchemy async session.
            actor_user_id: UUID of the user performing the action. Nullable for
                system-initiated actions.
            resource_id: String representation of the entity primary key.
            changes_before: Field snapshot before the mutation.
            changes_after: Field snapshot after the mutation.
            ip_address: Source IP of the HTTP request (HIPAA §164.312(b)).
                Extracted from X-Forwarded-For or direct client address.
            user_agent: HTTP User-Agent header value (HIPAA §164.312(b)).
            **_ignored_kwargs: Additional keyword arguments are silently ignored
                to allow callers to pass domain-specific metadata without
                raising TypeError.

        Returns:
            Persisted AuditLogEntry.

        Raises:
            SQLAlchemyError: If the database write fails.
        """
        entry = AuditLogEntry(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes_before=changes_before,
            changes_after=changes_after,
        )
        session.add(entry)
        await session.flush()
        logger.info(
            "audit: action=%s resource_type=%s resource_id=%s actor=%s tenant=%s",
            action,
            resource_type,
            resource_id,
            actor_user_id,
            tenant_id,
        )
        return entry


# Deprecated in 1.5.0 in favour of adaptix_contracts.schemas.audit_contracts
# (the standalone Audit service surface). Retained for backward compatibility.
__deprecated__ = True

__all__ = ["AuditServiceClient", "AuditLogEntry"]
