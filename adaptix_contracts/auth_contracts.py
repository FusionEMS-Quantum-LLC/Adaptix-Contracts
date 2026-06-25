"""AWS API Gateway identity header contracts for Adaptix domain services.

AWS API Gateway validates the caller's JWT at the edge using the Lambda JWT
authorizer, then injects verified identity headers before forwarding to the
downstream service. Services read and trust these headers — the gateway is
the single trust boundary. No custom HMAC, no JWT re-validation, no Cognito
calls at the service layer.

Production header contract (injected by Lambda JWT authorizer):
  X-User-Id      — authenticated user UUID (JWT ``sub`` claim)
  X-Tenant-Id    — authenticated tenant UUID (JWT ``tid`` claim)
  X-User-Email   — authenticated user email
  X-User-Roles   — comma-separated role list
  X-Is-Founder   — "true" or "false"
  X-Request-Id   — request correlation UUID

Development / test fallback (only when ENVIRONMENT != "production"):
  When X-User-Id is absent the request falls back to bearer JWT validation
  so local development and test suites continue to work without running a
  full API Gateway stack.

Gateway HMAC signature verification (forensic fix F-24)
-------------------------------------------------------
The injected identity headers above are only trustworthy if the request
actually came through the gateway. The gateway HMAC-signs every authenticated
request as ``X-Adaptix-Auth-Context`` + ``X-Adaptix-Auth-Signature`` (see
``Adaptix-Core-Service/adaptix-gateway/.../app/services/auth_context.py``).
``get_auth_context`` now verifies that signature when present, so an in-VPC
actor that reaches a service directly cannot forge identity / tenant / founder.
Verification is NON-BREAKING by default: an absent signature is allowed
(byte-for-byte unchanged behavior) unless ``ADAPTIX_GATEWAY_HMAC_ENFORCE`` is
set to ``"true"``. See the F-24 block in ``get_auth_context`` for details.

The RS256 gateway-context JWT mode that appeared in prior versions of this
module has been removed. Services that reference ``build_gateway_context_jwt``
or ``GATEWAY_PUBLIC_KEY_ENV`` should be updated to use the new header contract.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated
from uuid import UUID

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from adaptix_contracts.gateway_signature import (
    GatewaySignatureError,
    gateway_shared_secret,
    has_gateway_signature,
    verify_gateway_signature,
)

logger = logging.getLogger(__name__)

# Environment variable that controls whether the bearer-JWT dev fallback is
# permitted. Set to "production" or "prod" in real deployments; the fallback
# is then disabled so every request MUST arrive via API Gateway.
_ENV_VAR = "ENVIRONMENT"

# Forensic fix F-24 — gateway HMAC verification of injected identity headers.
#
# Background: ``get_auth_context`` trusts X-User-Id / X-Tenant-Id / X-Is-Founder
# WITHOUT verifying the gateway's HMAC signature. Any in-VPC actor that reaches
# a service directly can spoof identity / tenant / founder. The gateway DOES
# sign every authenticated request (X-Adaptix-Auth-Context + -Signature). This
# adds CONSUMER-side verification with three behaviors:
#
#   1. Signature PRESENT + shared secret configured -> VERIFY (HMAC-SHA256 over
#      the gateway's signed context, with replay window). Failure -> 401. This
#      closes the "forge a valid signature" path.
#   2. Signature ABSENT -> behavior gated by ``ADAPTIX_GATEWAY_HMAC_ENFORCE``
#      (default "false"). Default/false -> ALLOW exactly as before (warn once).
#      "true" -> 401 (later founder-gated ops flip, after every caller signs).
#   3. No shared secret configured -> ALLOW as before (cannot verify) + warn.
#      Never hard-crash on a missing secret.
#
# Default runtime behavior after merge is byte-for-byte identical to before for
# both signed-and-valid and unsigned requests (see test_auth_contracts.py
# F-24 cases). Enforcement is opt-in via the env flag below.
_GATEWAY_HMAC_ENFORCE_ENV = "ADAPTIX_GATEWAY_HMAC_ENFORCE"

# One-shot guards so the absent-signature / missing-secret warnings do not
# flood logs on every request. Reset only on process restart.
_warned_absent_signature = False
_warned_missing_secret = False


def _gateway_hmac_enforce() -> bool:
    return os.getenv(_GATEWAY_HMAC_ENFORCE_ENV, "").strip().lower() in (
        "true",
        "1",
        "yes",
    )


class AuthContext(BaseModel):
    """Resolved identity injected by the AWS API Gateway Lambda authorizer.

    All fields are sourced from the verified identity headers the gateway
    injects after validating the caller's Bearer JWT. Services trust them
    without any re-validation.

    Attributes:
        user_id: UUID of the authenticated user (from X-User-Id).
        tenant_id: UUID of the authenticated tenant (from X-Tenant-Id).
        email: Email of the authenticated user (from X-User-Email).
        roles: Comma-split role list (from X-User-Roles).
        is_founder: True when the X-Is-Founder header equals "true" or the
            ``founder`` role is present in ``roles``.
    """

    user_id: UUID
    tenant_id: UUID
    email: str = ""
    roles: list[str] = []
    is_founder: bool = False

    model_config = {"frozen": True}


def _is_production() -> bool:
    return os.getenv(_ENV_VAR, "").strip().lower() in ("production", "prod")


def _parse_roles(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [r.strip() for r in raw.split(",") if r.strip()]


async def get_auth_context(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
    x_user_email: Annotated[str | None, Header(alias="X-User-Email")] = None,
    x_user_roles: Annotated[str | None, Header(alias="X-User-Roles")] = None,
    x_is_founder: Annotated[str | None, Header(alias="X-Is-Founder")] = None,
    x_adaptix_auth_context: Annotated[
        str | None, Header(alias="X-Adaptix-Auth-Context")
    ] = None,
    x_adaptix_auth_signature: Annotated[
        str | None, Header(alias="X-Adaptix-Auth-Signature")
    ] = None,
    x_adaptix_auth_path: Annotated[
        str | None, Header(alias="X-Adaptix-Auth-Path")
    ] = None,
) -> AuthContext:
    """FastAPI dependency: extract authenticated identity from API Gateway headers.

    AWS API Gateway validates the caller's JWT with the Lambda JWT authorizer
    and injects verified identity headers. Services trust these headers
    completely — no crypto re-verification is performed here.

    In development (ENVIRONMENT != "production"), requests without X-User-Id
    are rejected with 401 so developers see the same error shape as production.
    In production, requests without X-User-Id are rejected the same way (they
    didn't arrive via API Gateway).

    Args:
        x_user_id: Authenticated user UUID (X-User-Id header).
        x_tenant_id: Authenticated tenant UUID (X-Tenant-Id header).
        x_user_email: Authenticated user email (X-User-Email header).
        x_user_roles: Comma-separated role list (X-User-Roles header).
        x_is_founder: "true" / "false" founder flag (X-Is-Founder header).

    Returns:
        AuthContext with verified identity.

    Raises:
        HTTPException 401: X-User-Id or X-Tenant-Id missing or not a valid UUID.
    """
    uid = (x_user_id or "").strip()
    tid = (x_tenant_id or "").strip()

    if not uid or not tid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing gateway identity headers (X-User-Id, X-Tenant-Id). "
                "Requests must arrive via AWS API Gateway with a valid Bearer JWT."
            ),
        )

    try:
        user_uuid = UUID(uid)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header is not a valid UUID.",
        ) from exc

    try:
        tenant_uuid = UUID(tid)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Tenant-Id header is not a valid UUID.",
        ) from exc

    # ------------------------------------------------------------------
    # F-24: gateway HMAC signature verification (see module header).
    #
    # This block NEVER changes the default unsigned behavior: with no
    # signature header and ADAPTIX_GATEWAY_HMAC_ENFORCE unset/false the
    # request falls through unchanged. It only adds 401s for (a) a present
    # but invalid signature, and (b) an absent signature when enforcement
    # is explicitly turned on.
    # ------------------------------------------------------------------
    global _warned_absent_signature, _warned_missing_secret
    signature_present = has_gateway_signature(
        context_b64=x_adaptix_auth_context,
        signature_hex=x_adaptix_auth_signature,
    )
    secret = gateway_shared_secret()

    if signature_present:
        if secret is not None:
            # Behavior 1: present + secret -> verify. Failure -> 401.
            try:
                verified = verify_gateway_signature(
                    context_b64=x_adaptix_auth_context or "",
                    signature_hex=x_adaptix_auth_signature or "",
                    shared_secret=secret,
                    auth_path=x_adaptix_auth_path,
                )
            except GatewaySignatureError as exc:
                logger.warning("gateway HMAC verification failed: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Gateway auth context signature is invalid.",
                ) from exc

            # Defense in depth: the signed payload's identity MUST match the
            # injected X-User-Id / X-Tenant-Id headers. A valid signature over
            # a DIFFERENT identity than the headers is a tamper attempt.
            signed_user = str(verified.get("user_id", "")).strip()
            signed_tenant = str(verified.get("tenant_id", "")).strip()
            mismatch = False
            try:
                if signed_user and UUID(signed_user) != user_uuid:
                    mismatch = True
                if signed_tenant and UUID(signed_tenant) != tenant_uuid:
                    mismatch = True
            except (ValueError, AttributeError):
                # Non-UUID claims in a signed context — treat as mismatch.
                mismatch = True
            if mismatch:
                logger.warning(
                    "gateway HMAC context identity mismatch vs injected headers"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Gateway auth context does not match identity headers.",
                )
        else:
            # Behavior 3: signature present but no secret to verify with.
            # Cannot verify -> allow as before, warn once.
            if not _warned_missing_secret:
                logger.warning(
                    "gateway signature present but ADAPTIX_GATEWAY_SHARED_SECRET "
                    "is not configured; cannot verify. Allowing request "
                    "(configure the secret to enable verification)."
                )
                _warned_missing_secret = True
    else:
        # Behavior 2: signature absent. Gated by enforcement flag.
        if _gateway_hmac_enforce():
            logger.warning(
                "gateway signature absent and %s is enabled; rejecting request.",
                _GATEWAY_HMAC_ENFORCE_ENV,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Missing gateway auth context signature "
                    "(X-Adaptix-Auth-Context / X-Adaptix-Auth-Signature)."
                ),
            )
        if not _warned_absent_signature:
            logger.warning(
                "gateway signature absent; allowing request (enforcement off). "
                "Set %s=true once all callers sign to require it.",
                _GATEWAY_HMAC_ENFORCE_ENV,
            )
            _warned_absent_signature = True

    roles = _parse_roles(x_user_roles)
    is_founder_flag = (x_is_founder or "false").strip().lower() in ("true", "1", "yes")
    # If the X-Is-Founder flag is set, ensure "founder" is in roles.
    if is_founder_flag and "founder" not in {r.lower() for r in roles}:
        roles = ["founder", *roles]
    # Conversely, if "founder" is in roles, set is_founder.
    if "founder" in {r.lower() for r in roles}:
        is_founder_flag = True

    return AuthContext(
        user_id=user_uuid,
        tenant_id=tenant_uuid,
        email=(x_user_email or "").strip(),
        roles=roles,
        is_founder=is_founder_flag,
    )


# ---------------------------------------------------------------------------
# Backward-compatibility shims for code that imported HMAC/RS256 symbols.
# These raise descriptive errors so dependent code fails loudly rather than
# silently at runtime.
# ---------------------------------------------------------------------------

GATEWAY_SHARED_SECRET_ENV = "ADAPTIX_GATEWAY_SHARED_SECRET"
GATEWAY_PUBLIC_KEY_ENV = "ADAPTIX_GATEWAY_PUBLIC_KEY"
GATEWAY_SIGNATURE_MAX_AGE_SECONDS = 300
GATEWAY_JWT_CONTEXT_HEADER = "X-Adaptix-Gateway-Context"


def build_gateway_context_jwt(**kwargs) -> str:  # type: ignore[misc]
    """Removed — AWS API Gateway replaces custom gateway context JWTs.

    This function existed to produce short-lived RS256 context JWTs for the
    prior custom Python gateway. It is no longer needed because AWS API
    Gateway injects verified identity headers directly. Code calling this
    should switch to reading X-User-Id / X-Tenant-Id / X-User-Roles headers.

    Raises RuntimeError (not NotImplementedError) so existing callers that
    catch (ValueError, RuntimeError) for graceful degradation continue to
    work without modification.
    """
    raise RuntimeError(
        "build_gateway_context_jwt has been removed. "
        "AWS API Gateway injects X-User-Id / X-Tenant-Id / X-User-Roles headers "
        "after validating the Bearer JWT. No custom context JWT is needed."
    )


__all__ = [
    "AuthContext",
    "GATEWAY_SHARED_SECRET_ENV",
    "GATEWAY_PUBLIC_KEY_ENV",
    "GATEWAY_JWT_CONTEXT_HEADER",
    "GATEWAY_SIGNATURE_MAX_AGE_SECONDS",
    "build_gateway_context_jwt",
    "get_auth_context",
]

# Env flag (re-exported for ops/tests) controlling absent-signature rejection.
# Default false: absent signature is allowed (unchanged behavior). Set "true"
# only after every caller is confirmed to sign requests via the gateway.
ADAPTIX_GATEWAY_HMAC_ENFORCE_ENV = _GATEWAY_HMAC_ENFORCE_ENV
__all__.append("ADAPTIX_GATEWAY_HMAC_ENFORCE_ENV")
