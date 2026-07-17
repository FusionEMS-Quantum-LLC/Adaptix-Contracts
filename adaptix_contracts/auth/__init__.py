"""Adaptix auth context contracts."""

from adaptix_contracts.auth.context import (
    AdaptixRole,
    AdaptixRoleSet,
    AdaptixTenantContext,
    AdaptixAuthContext,
    AdaptixServiceContext,
    AdaptixSignedInternalContext,
)
from adaptix_contracts.auth.module_entitlement_gate import (
    require_module_entitlement,
)
from adaptix_contracts.auth.service_token import (
    DEFAULT_TTL_SECONDS,
    SERVICE_TOKEN_VERSION,
    ServiceTokenAuthzError,
    ServiceTokenClaims,
    ServiceTokenError,
    issue_service_token,
    verify_service_token,
)

__all__ = [
    "AdaptixRole",
    "AdaptixRoleSet",
    "AdaptixTenantContext",
    "AdaptixAuthContext",
    "AdaptixServiceContext",
    "AdaptixSignedInternalContext",
    "require_module_entitlement",
    # Canonical S2S service-identity token (Operations -> CAD/Air).
    "issue_service_token",
    "verify_service_token",
    "ServiceTokenClaims",
    "ServiceTokenError",
    "ServiceTokenAuthzError",
    "SERVICE_TOKEN_VERSION",
    "DEFAULT_TTL_SECONDS",
]
