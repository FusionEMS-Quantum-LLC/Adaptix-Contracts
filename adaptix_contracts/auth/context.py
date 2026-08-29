"""
Adaptix Shared Auth Context Contracts
======================================
Canonical auth/tenant/role context models used by ALL backend services.

Rules:
- Every service must derive tenant context from AdaptixAuthContext, NOT from raw headers.
- Internal service calls must use AdaptixSignedInternalContext.
- Never trust X-Tenant-ID or X-User-ID headers directly.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, cast
from pydantic import BaseModel, Field
import uuid


class AdaptixRole(str, Enum):
    """Recognized identity-role strings for verified token parsing.

    Agency-assignable values must match ``AgencyRole`` in
    ``adaptix_contracts.auth.agency_roles``. Platform-only values must match
    ``PlatformOnlyRole``. Occupation titles below are recognized on the wire
    so a legacy claim is not silently dropped; they are not a second agency
    assignment catalog.
    """

    FOUNDER = "founder"
    SUPER_ADMIN = "super_admin"
    PLATFORM_ADMIN = "platform_admin"
    TENANT_ADMIN = "tenant_admin"
    AGENCY_ADMIN = "agency_admin"
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    CAD_SUPERVISOR = "cad_supervisor"
    DISPATCHER = "dispatcher"
    CREW_MEMBER = "crew_member"
    BILLING_ADMIN = "billing_admin"
    BILLING_OPERATOR = "billing_operator"
    OPERATOR = "operator"
    FIELD_USER = "field_user"
    MEDICAL_DIRECTOR = "medical_director"
    ASSISTANT_MEDICAL_DIRECTOR = "assistant_medical_director"
    QA_REVIEWER = "qa_reviewer"
    VIEWER = "viewer"
    SERVICE_ACCOUNT = "service_account"
    # Occupation / domain titles — parseable, not agency-assignable.
    PARAMEDIC = "paramedic"
    EMT = "emt"
    FIREFIGHTER = "firefighter"
    PILOT = "pilot"
    BILLING_SPECIALIST = "billing_specialist"
    WORKFORCE_MANAGER = "workforce_manager"
    INVENTORY_MANAGER = "inventory_manager"
    NARCOTICS_OFFICER = "narcotics_officer"
    READ_ONLY = "read_only"


class AdaptixRoleSet(BaseModel):
    """Verified role set for an authenticated user."""

    roles: list[AdaptixRole] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    entitlements: list[str] = Field(default_factory=list)

    def has_role(self, role: AdaptixRole) -> bool:
        return role in self.roles

    def has_any_role(self, *roles: AdaptixRole) -> bool:
        return any(r in self.roles for r in roles)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def is_founder(self) -> bool:
        return AdaptixRole.FOUNDER in self.roles

    def is_agency_admin(self) -> bool:
        return AdaptixRole.AGENCY_ADMIN in self.roles

    def is_medical_director(self) -> bool:
        """Clinical authority who owns/signs the agency protocol library (MD module gate)."""
        return AdaptixRole.MEDICAL_DIRECTOR in self.roles

    def is_service_account(self) -> bool:
        return AdaptixRole.SERVICE_ACCOUNT in self.roles


class AdaptixTenantContext(BaseModel):
    """Verified tenant context derived from auth token — never from raw headers."""

    tenant_id: str = Field(..., description="Verified tenant UUID")
    agency_name: str | None = None
    agency_slug: str | None = None
    modules_enabled: list[str] = Field(default_factory=list)
    is_active: bool = True

    def has_module(self, module: str) -> bool:
        return module in self.modules_enabled


def _known_adaptix_role(role: str) -> AdaptixRole | None:
    """Return the enum member for a recognized role string, else None."""
    try:
        return AdaptixRole(role)
    except ValueError:
        return None


def _token_string_items(value: object) -> list[str]:
    """Collect non-empty strings from a sequence claim."""
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    items: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        text = entry.strip()
        if text:
            items.append(text)
    return items


def _token_string_list(value: object) -> list[str]:
    """Return string items from a token claim, treating null as empty.

    An explicit JSON ``null`` must not iterate. Non-string entries are
    dropped rather than coerced, so a poisoned claim cannot invent roles.
    """
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return _token_string_items(value)


class AdaptixAuthContext(BaseModel):
    """
    Complete verified auth context for an authenticated request.

    This is the ONLY trusted source of identity in Adaptix services.
    Derived from a verified JWT token — never from client-supplied headers.
    """

    user_id: str = Field(..., description="Verified user UUID")
    tenant_id: str = Field(
        ..., description="Verified tenant UUID — same as tenant_context.tenant_id"
    )
    session_id: str = Field(..., description="Active session UUID")
    email: str | None = None
    full_name: str | None = None
    role_set: AdaptixRoleSet = Field(default_factory=AdaptixRoleSet)
    tenant_context: AdaptixTenantContext
    is_founder: bool = False
    is_service_account: bool = False
    token_jti: str | None = None  # JWT ID for revocation checks

    @classmethod
    def from_token_payload(
        cls,
        payload: dict[str, Any],
        trusted_tenant_id: str | None = None,
    ) -> "AdaptixAuthContext":
        """Construct from verified JWT payload."""
        tenant_id = payload.get("tenant_id")
        user_id = payload.get("sub")
        session_id = payload.get("session_id")

        missing_fields = [
            field_name
            for field_name, field_value in (
                ("tenant_id", tenant_id),
                ("sub", user_id),
                ("session_id", session_id),
            )
            if not field_value
        ]
        if missing_fields:
            raise ValueError(
                "Missing required token payload fields: " + ", ".join(missing_fields)
            )

        # The guard above has already rejected a payload where any of these three
        # is absent or empty, so each is a present, non-empty claim by the time
        # execution reaches here. A type checker cannot follow that narrowing -
        # it happens through a list comprehension over tuples, deliberately, so
        # that ONE error names every missing field instead of failing on the
        # first. `typing.cast` states the invariant the guard already enforces
        # and is a documented no-op at runtime: it returns its second argument
        # unchanged, so behaviour, validation and error messages are identical.
        #
        # This is not cosmetic. `payload.get(...)` on a `dict[str, Any]` is typed
        # `Any | None`, and `user_id`/`tenant_id`/`session_id` are declared `str`,
        # so the constructor call below is a genuine type error - one a consumer
        # sees and this repository did not, because the pydantic mypy plugin's
        # `init_typed` defaults to False and therefore types every synthesised
        # `__init__` argument as `Any`. mypy-consumer-view.ini is what surfaced
        # it. Do not re-hide it by widening that config.
        user_id = cast(str, user_id)
        tenant_id = cast(str, tenant_id)
        session_id = cast(str, session_id)

        if trusted_tenant_id is not None and tenant_id != trusted_tenant_id:
            raise ValueError(
                f"Token tenant_id mismatch: payload={tenant_id}, trusted={trusted_tenant_id}"
            )

        roles = [
            parsed
            for role in _token_string_list(payload.get("roles"))
            if (parsed := _known_adaptix_role(role)) is not None
        ]
        permissions = _token_string_list(payload.get("permissions"))
        entitlements = _token_string_list(payload.get("entitlements"))
        modules = _token_string_list(payload.get("modules_enabled"))

        return cls(
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            email=payload.get("email"),
            full_name=payload.get("full_name"),
            role_set=AdaptixRoleSet(
                roles=roles,
                permissions=permissions,
                entitlements=entitlements,
            ),
            tenant_context=AdaptixTenantContext(
                tenant_id=tenant_id,
                agency_name=payload.get("agency_name"),
                agency_slug=payload.get("agency_slug"),
                modules_enabled=modules,
                is_active=payload.get("tenant_active", True),
            ),
            is_founder=AdaptixRole.FOUNDER in roles,
            is_service_account=AdaptixRole.SERVICE_ACCOUNT in roles,
            token_jti=payload.get("jti"),
        )


class AdaptixServiceContext(BaseModel):
    """
    Context for internal service-to-service calls.
    Must be signed by the gateway or originating service.
    """

    source_service: str = Field(..., description="Originating service name")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    tenant_id: str = Field(..., description="Tenant scope for this call")
    actor_id: str | None = None  # User who initiated the chain
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signature: str | None = None  # HMAC signature for verification


class AdaptixSignedInternalContext(BaseModel):
    """
    Signed internal context passed between services.
    Services MUST verify the signature before trusting this context.
    """

    service_context: AdaptixServiceContext
    auth_context: AdaptixAuthContext | None = None
    signature_verified: bool = False
    forwarded_at: str | None = None

    def is_trusted(self) -> bool:
        """Returns True only if signature has been verified."""
        return self.signature_verified
