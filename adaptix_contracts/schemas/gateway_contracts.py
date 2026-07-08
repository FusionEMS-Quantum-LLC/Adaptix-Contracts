"""Gateway routing contracts.

Typed contracts for the newly-separated Adaptix Core gateway. Describe the
route-registry entries that map a path prefix to a target domain service and
the forwarded request context propagated to downstream services after edge
authentication.
"""

from pydantic import BaseModel, Field


class GatewayRouteRegistryEntry(BaseModel):
    """A single gateway route-registry entry mapping a prefix to a service."""

    path_prefix: str = Field(
        ..., description="Route path prefix handled by the gateway"
    )
    target_service: str = Field(
        ..., description="Downstream domain service for the prefix"
    )
    auth_required: bool = Field(..., description="Whether authentication is required")
    founder_only: bool = Field(..., description="Whether the route is founder-only")


class ForwardedRequestContext(BaseModel):
    """Identity/context forwarded to downstream services after edge auth."""

    tenant_id: str = Field(..., description="Tenant ID")
    user_id: str | None = Field(
        None, description="Authenticated user identifier, if any"
    )
    correlation_id: str = Field(..., description="Request correlation identifier")
    is_founder: bool = Field(..., description="Whether the caller is a founder")
    roles: list[str] = Field(
        default_factory=list, description="Caller role identifiers"
    )
