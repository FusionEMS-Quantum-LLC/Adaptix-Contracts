"""Adaptix Cognito Auth Contracts.

Shared contract objects for Amazon Cognito JWT validation across all Adaptix services.

Architecture:
- Amazon Cognito User Pools = primary authentication authority
- Microsoft Entra ID = optional enterprise SSO through Cognito federation
- Adaptix = authorization source of truth (tenant, roles, permissions)
- Microsoft Graph = post-auth enrichment only (disabled by default)

Rules:
- Public clients must NEVER set X-User-ID, X-Tenant-ID, X-User-Email directly
- Only the gateway may inject those headers after Cognito JWT validation
- Adaptix controls all authorization decisions
- Microsoft login alone does NOT grant Adaptix access
"""

from __future__ import annotations

from typing import Optional

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

# ─── Cognito Configuration ────────────────────────────────────────────────────


@dataclass
class AdaptixCognitoConfig:
    """Cognito User Pool configuration for JWT validation."""

    region: str
    user_pool_id: str
    client_id: str
    issuer: str
    jwks_url: str
    allowed_audiences: list[str] = field(default_factory=list)
    allowed_token_use_values: list[str] = field(
        default_factory=lambda: ["access", "id"]
    )
    required_claims: list[str] = field(
        default_factory=lambda: ["sub", "iss", "exp", "iat", "token_use"]
    )
    clock_skew_seconds: int = 30

    @classmethod
    def from_env(cls) -> "AdaptixCognitoConfig":
        """Build config from environment variables."""
        import os

        region = os.environ.get("COGNITO_REGION", "us-east-1")
        user_pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
        client_id = os.environ.get(
            "COGNITO_CLIENT_ID", os.environ.get("COGNITO_CLIENT_ID_WEB", "")
        )
        issuer = os.environ.get(
            "COGNITO_ISSUER",
            f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
            if user_pool_id
            else "",
        )
        jwks_url = os.environ.get(
            "COGNITO_JWKS_URL", f"{issuer}/.well-known/jwks.json" if issuer else ""
        )
        return cls(
            region=region,
            user_pool_id=user_pool_id,
            client_id=client_id,
            issuer=issuer,
            jwks_url=jwks_url,
            allowed_audiences=[client_id] if client_id else [],
        )

    @property
    def is_configured(self) -> bool:
        """Return True if Cognito is configured."""
        return bool(
            self.user_pool_id and self.client_id and self.issuer and self.jwks_url
        )


# ─── Cognito Claims ───────────────────────────────────────────────────────────


class AdaptixCognitoClaims(BaseModel):
    """Validated Cognito JWT claims."""

    # Standard JWT claims
    sub: str
    iss: str
    exp: int
    iat: int
    token_use: str  # "access" or "id"

    # Cognito-specific
    cognito_username: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    cognito_groups: Optional[list[str]] = None

    # Adaptix custom attributes (set by admin)
    custom_adaptix_user_id: str | None = None
    custom_adaptix_tenant_id: str | None = None
    custom_adaptix_agency_id: str | None = None
    custom_adaptix_roles: str | None = None  # JSON string of roles list

    # Optional Microsoft federation fields (when Entra is federated through Cognito)
    identities: Optional[list[dict]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",  # Allow additional Cognito claims
    )

    @classmethod
    def from_raw_claims(cls, claims: dict) -> "AdaptixCognitoClaims":
        """Build from raw JWT claims dict, mapping Cognito field names."""
        mapped = {
            "sub": claims.get("sub", ""),
            "iss": claims.get("iss", ""),
            "exp": claims.get("exp", 0),
            "iat": claims.get("iat", 0),
            "token_use": claims.get("token_use", ""),
            "cognito_username": claims.get("cognito:username"),
            "email": claims.get("email"),
            "email_verified": claims.get("email_verified"),
            "cognito_groups": claims.get("cognito:groups"),
            "custom_adaptix_user_id": claims.get("custom:adaptix_user_id"),
            "custom_adaptix_tenant_id": claims.get("custom:adaptix_tenant_id"),
            "custom_adaptix_agency_id": claims.get("custom:adaptix_agency_id"),
            "custom_adaptix_roles": claims.get("custom:adaptix_roles"),
            "identities": claims.get("identities"),
        }
        return cls(**{k: v for k, v in mapped.items() if v is not None})


# ─── Auth Context ─────────────────────────────────────────────────────────────


class AdaptixAuthContext(BaseModel):
    """
    Verified Adaptix auth context — built from validated Cognito JWT.

    This is the ONLY trusted source of identity in Adaptix services.
    Built by the gateway after Cognito JWT validation.
    Never built from raw client-supplied headers.
    """

    # Identity
    subject: str  # Cognito sub (stable user identifier)
    provider: str  # "cognito" | "cognito_entra_federation"
    provider_user_id: str  # Cognito sub or federated provider subject
    email: str | None = None
    email_verified: bool = False
    display_name: str | None = None

    # Adaptix identity (resolved from Cognito claims + DB lookup)
    user_id: str | None = None  # Adaptix user UUID
    tenant_id: str | None = None  # Adaptix tenant UUID
    agency_id: str | None = None  # Adaptix agency UUID

    # Authorization (controlled by Adaptix, not Cognito)
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    modules_enabled: list[str] = field(default_factory=list)
    is_founder: bool = False
    is_service_account: bool = False

    # Token metadata
    source_token_issuer: str | None = None
    token_use: str | None = None  # "access" or "id"

    # Tracing
    correlation_id: str | None = None
    trace_id: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.subject)

    @property
    def has_tenant(self) -> bool:
        return bool(self.tenant_id)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    def has_module(self, module: str) -> bool:
        return module in self.modules_enabled


# ─── Internal Service Context ─────────────────────────────────────────────────


class AdaptixServiceContext(BaseModel):
    """
    Internal service-to-service context.
    Injected by gateway after Cognito JWT validation.
    Domain services must verify this is gateway-originated.
    """

    source_service: str
    correlation_id: str
    causation_id: str | None = None
    tenant_id: str
    user_id: str | None = None
    request_id: str | None = None
    internal_auth_marker: str | None = None  # Signed marker proving gateway origin


class AdaptixSignedInternalContext(BaseModel):
    """
    Signed internal context passed between services.
    Services MUST verify the internal_auth_marker before trusting.
    """

    service_context: AdaptixServiceContext
    auth_context: AdaptixAuthContext | None = None
    signature_verified: bool = False

    def is_trusted(self) -> bool:
        return self.signature_verified and bool(
            self.service_context.internal_auth_marker
        )


# ─── Constants ────────────────────────────────────────────────────────────────

COGNITO_PRODUCTION_USER_POOL_ID = "us-east-1_hUiicvQ6c"
COGNITO_PRODUCTION_WEB_CLIENT_ID = "2d2q79if6tn73arapedf471mkt"
COGNITO_PRODUCTION_ANDROID_CLIENT_ID = "2od459phr0mauh4kkjhq3b0d5i"
COGNITO_PRODUCTION_ISSUER = (
    "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_hUiicvQ6c"
)
COGNITO_PRODUCTION_JWKS_URL = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_hUiicvQ6c/.well-known/jwks.json"
COGNITO_PRODUCTION_DOMAIN = "adaptix-production.auth.us-east-1.amazoncognito.com"
COGNITO_PRODUCTION_HOSTED_UI = (
    "https://adaptix-production.auth.us-east-1.amazoncognito.com/login"
)
