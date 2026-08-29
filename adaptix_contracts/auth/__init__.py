"""Adaptix auth context contracts."""

from adaptix_contracts.auth.agency_roles import (
    AGENCY_ROLE_VALUES,
    PLATFORM_ONLY_ROLES,
    AgencyRole,
    PlatformOnlyRole,
    is_agency_role,
    is_platform_only,
    normalize_role,
)
from adaptix_contracts.auth.permissions import (
    CORE_ROLES_MANAGE,
    CORE_USERS_MANAGE,
    QA_PERMISSIONS,
    QA_PROTOCOL_MANAGE,
    QA_REVIEW,
    QA_SUPERVISE,
    WORKSPACE_ADMIN_ACCESS,
)
from adaptix_contracts.auth.context import (
    AdaptixRole,
    AdaptixRoleSet,
    AdaptixTenantContext,
    AdaptixAuthContext,
    AdaptixServiceContext,
    AdaptixSignedInternalContext,
)
from adaptix_contracts.auth.interoperability import (
    INTEROPERABILITY_CONSENT_READ_SCOPE,
    INTEROPERABILITY_IDENTITY_READ_SCOPE,
    INTEROPERABILITY_PAYLOAD_READ_SCOPE,
    INTEROPERABILITY_SCOPES,
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
    "AgencyRole",
    "PlatformOnlyRole",
    "AGENCY_ROLE_VALUES",
    "PLATFORM_ONLY_ROLES",
    "normalize_role",
    "is_agency_role",
    "is_platform_only",
    "WORKSPACE_ADMIN_ACCESS",
    "CORE_USERS_MANAGE",
    "CORE_ROLES_MANAGE",
    "QA_REVIEW",
    "QA_SUPERVISE",
    "QA_PROTOCOL_MANAGE",
    "QA_PERMISSIONS",
    "AdaptixRole",
    "AdaptixRoleSet",
    "AdaptixTenantContext",
    "AdaptixAuthContext",
    "AdaptixServiceContext",
    "AdaptixSignedInternalContext",
    "require_module_entitlement",
    # Canonical interoperability S2S scopes.
    "INTEROPERABILITY_PAYLOAD_READ_SCOPE",
    "INTEROPERABILITY_IDENTITY_READ_SCOPE",
    "INTEROPERABILITY_CONSENT_READ_SCOPE",
    "INTEROPERABILITY_SCOPES",
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
