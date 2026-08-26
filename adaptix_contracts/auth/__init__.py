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
from adaptix_contracts.auth.platform_token import (
    PLATFORM_TOKEN_VERSION,
    TOKEN_USE as PLATFORM_TOKEN_USE,
    PlatformServiceTokenAuthzError,
    PlatformServiceTokenClaims,
    PlatformServiceTokenError,
    issue_platform_service_token,
    verify_platform_service_token,
    verify_platform_service_token_with_keyset,
)
from adaptix_contracts.auth.service_token import (
    DEFAULT_TTL_SECONDS,
    SERVICE_TOKEN_VERSION,
    ServiceTokenAuthzError,
    ServiceTokenClaims,
    ServiceTokenError,
    issue_service_token,
    verify_service_token,
    verify_service_token_with_keyset,
)

__all__ = [
    "AdaptixRole",
    "AdaptixRoleSet",
    "AdaptixTenantContext",
    "AdaptixAuthContext",
    "AdaptixServiceContext",
    "AdaptixSignedInternalContext",
    "require_module_entitlement",
    # Canonical S2S service-identity token (Operations -> CAD/Air; MCP -> EPCR).
    # Tenant-BOUND — tenant_id is a required claim.
    "issue_service_token",
    "verify_service_token",
    "verify_service_token_with_keyset",
    "ServiceTokenClaims",
    "ServiceTokenError",
    "ServiceTokenAuthzError",
    "SERVICE_TOKEN_VERSION",
    "DEFAULT_TTL_SECONDS",
    # Canonical S2S PLATFORM token — genuinely TENANT-LESS calls only (e.g.
    # Core -> Calendar pre-signup marketing email). tenant_id is structurally
    # absent from PlatformServiceTokenClaims; do not use this for a call that
    # acts for a tenant, even indirectly — use service_token instead.
    "issue_platform_service_token",
    "verify_platform_service_token",
    "verify_platform_service_token_with_keyset",
    "PlatformServiceTokenClaims",
    "PlatformServiceTokenError",
    "PlatformServiceTokenAuthzError",
    "PLATFORM_TOKEN_VERSION",
    "PLATFORM_TOKEN_USE",
]
