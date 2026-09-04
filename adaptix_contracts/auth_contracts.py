"""AWS API Gateway identity header contracts for Adaptix domain services.

AWS API Gateway validates the caller's JWT at the edge using the Lambda JWT
authorizer, then injects verified identity headers before forwarding to the
downstream service. The gateway is the primary trust boundary; downstream,
``get_auth_context`` additionally verifies the gateway's HMAC-signed context
(see the F-24 section below). No JWT re-validation and no Cognito calls at
the service layer.

Production header contract (injected by Lambda JWT authorizer):
  X-User-Id      — authenticated user UUID (JWT ``sub`` claim)
  X-Tenant-Id    — authenticated tenant UUID (JWT ``tid`` claim)
  X-User-Email   — authenticated user email
  X-User-Roles   — comma-separated role list
  X-Is-Founder   — "true" or "false"
  X-Request-Id   — request correlation UUID

Development / test behavior (ENVIRONMENT != "production"):
  There is NO bearer-JWT fallback: a request without X-User-Id / X-Tenant-Id
  is rejected with 401 in every environment. What relaxes outside production
  is signature enforcement — an ABSENT gateway signature is allowed by
  default (see ``ADAPTIX_GATEWAY_HMAC_ENFORCE`` below) so local development
  and test suites work without a running gateway.

Gateway HMAC signature verification (forensic fix F-24)
-------------------------------------------------------
The injected identity headers above are only trustworthy if the request
actually came through the gateway. The gateway HMAC-signs every authenticated
request as ``X-Adaptix-Auth-Context`` + ``X-Adaptix-Auth-Signature`` (see
``Adaptix-Core-Service/adaptix-gateway/.../app/services/auth_context.py``).
``get_auth_context`` now verifies that signature when present, so an in-VPC
actor that reaches a service directly cannot forge identity / tenant / founder.
When the signature verifies, the signed payload is AUTHORITATIVE for
``roles`` / ``email`` / ``is_founder`` — the individually spoofable
``X-User-Roles`` / ``X-Is-Founder`` / ``X-User-Email`` headers are ignored, so a
holder of a valid signature for their own identity cannot escalate roles or
founder status via unsigned headers.

Fail-closed-by-default in production (APPSEC-CONTRACTS-UNSIGNED-HEADER-TRUST)
----------------------------------------------------------------------------
In production (``ENVIRONMENT`` in {``production``, ``prod``}) an UNSIGNED request
is REJECTED by default (401): an ALB-direct / in-VPC actor cannot reach a service
and have forged ``X-User-Id`` / ``X-Tenant-Id`` / ``X-Is-Founder`` headers
trusted. A service that still has a legitimate UNSIGNED intra-VPC caller opts OUT
explicitly by setting ``ADAPTIX_GATEWAY_HMAC_ENFORCE=false`` (migration escape
hatch). Outside production the default stays OFF so local development and test
suites work without a full gateway. Likewise, in production a signature that is
PRESENT but cannot be verified (no shared secret configured) is REJECTED
(fail-closed) rather than trusted. See the F-24 block in ``get_auth_context``.

Founder privilege floor on the unsigned path (APPSEC-CONTRACTS-UNSIGNED-FOUNDER-ESCALATION)
-------------------------------------------------------------------------------------------
The opt-out above (``ADAPTIX_GATEWAY_HMAC_ENFORCE=false``) keeps a service's
legitimate UNSIGNED intra-VPC callers working — but it also re-opens the
unsigned identity path, on which ``X-Is-Founder`` and ``X-User-Roles`` are plain
headers covered by no signature. In PRODUCTION, ``founder`` is therefore never
granted on that path: the request still proceeds with the caller's ordinary
roles, but the platform-owner privilege that lifts tenant scoping is refused and
the demotion is logged at WARNING. This REJECTS NOTHING, so it is safe to run
ahead of the per-service HMAC enforcement rollout. Outside production the
behaviour is unchanged so dev/test can still simulate a founder with headers.

The RS256 gateway-context JWT mode that appeared in prior versions of this
module has been removed. Services that reference ``build_gateway_context_jwt``
or ``GATEWAY_PUBLIC_KEY_ENV`` should be updated to use the new header contract.
"""

from __future__ import annotations

import json
import logging
import os
from typing import cast, Annotated
from uuid import UUID

from fastapi import Header, HTTPException, Request, status
from pydantic import BaseModel

from adaptix_contracts.gateway_keys import has_verification_keys
from adaptix_contracts.gateway_signature import (
    GATEWAY_SHARED_SECRET_ENV,
    GatewaySignatureError,
    gateway_shared_secret,
    has_gateway_signature,
    verify_gateway_signature_for_request,
)

logger = logging.getLogger(__name__)

# Environment variable that controls whether the bearer-JWT dev fallback is
# permitted. Set to "production" or "prod" in real deployments; the fallback
# is then disabled so every request MUST arrive via API Gateway.
_ENV_VAR = "ENVIRONMENT"

# Forensic fix F-24 / APPSEC-CONTRACTS-UNSIGNED-HEADER-TRUST — gateway HMAC
# verification of injected identity headers.
#
# Background: ``get_auth_context`` trusted X-User-Id / X-Tenant-Id / X-Is-Founder
# WITHOUT verifying the gateway's HMAC signature. Any in-VPC actor that reaches
# a service directly (e.g. ALB-direct device / voice routes that bypass the
# gateway) can spoof identity / tenant / founder. The gateway DOES sign every
# authenticated request (X-Adaptix-Auth-Context + -Signature). This adds
# CONSUMER-side verification with three behaviors:
#
#   1. Signature PRESENT + shared secret configured -> VERIFY (HMAC-SHA256 over
#      the gateway's signed context, with replay window). Failure -> 401. This
#      closes the "forge a valid signature" path.
#   2. Signature ABSENT -> behavior gated by ``ADAPTIX_GATEWAY_HMAC_ENFORCE``.
#      In PRODUCTION the default is fail-closed: an absent signature is REJECTED
#      (401) unless ``ADAPTIX_GATEWAY_HMAC_ENFORCE`` is EXPLICITLY set to a
#      false-y value (opt-out migration escape hatch for a service with a legit
#      unsigned intra-VPC caller). Outside production the default stays OFF ->
#      ALLOW exactly as before (warn once) so dev/test work without a gateway.
#      An explicit "true"/"1"/"yes" forces enforcement in any environment.
#   3. Signature PRESENT but no shared secret configured -> in PRODUCTION this is
#      fail-closed (503): a signed request that cannot be verified must not be
#      trusted. Outside production it is ALLOW + warn (cannot verify) as before.
#      Never hard-crash on a missing secret in non-production.
#
# The prod default is fail-closed on unsigned requests. Before the fleet re-pins
# this version, each service with a legitimate UNSIGNED intra-VPC caller must set
# ``ADAPTIX_GATEWAY_HMAC_ENFORCE=false`` explicitly (see PR rollout warning).
_GATEWAY_HMAC_ENFORCE_ENV = "ADAPTIX_GATEWAY_HMAC_ENFORCE"

# One-shot guards so the absent-signature / missing-secret warnings do not
# flood logs on every request. Reset only on process restart.
_warned_absent_signature = False
_warned_missing_secret = False


_TRUEY = ("true", "1", "yes")
_FALSEY = ("false", "0", "no")

# The single highest-privilege role on the platform. Founder lifts tenant
# scoping on cross-tenant reads, so it is the one role that must never be
# grantable by a header nobody signed. See the privilege floor in
# ``get_auth_context`` (APPSEC-CONTRACTS-UNSIGNED-FOUNDER-ESCALATION).
_FOUNDER_ROLE = "founder"


def _gateway_hmac_enforce() -> bool:
    """Whether an ABSENT gateway signature must be rejected (fail-closed).

    Resolution order (safe-by-default in production):

    * ``ADAPTIX_GATEWAY_HMAC_ENFORCE`` explicitly true-y (``true``/``1``/``yes``)
      -> ``True`` in any environment (force enforcement).
    * ``ADAPTIX_GATEWAY_HMAC_ENFORCE`` explicitly false-y (``false``/``0``/``no``)
      -> ``False`` in any environment. This is the opt-out migration escape
      hatch for a service that still has a legitimate UNSIGNED intra-VPC caller.
    * Unset / blank / unrecognized -> environment default: ``True`` in
      production (``ENVIRONMENT`` in {``production``, ``prod``}), else ``False``.

    The production default is fail-closed: an unsigned request is rejected unless
    a service explicitly opts out. This closes the forged-header trust path on
    ALB-direct / in-VPC routes that bypass the gateway.
    """
    raw = os.getenv(_GATEWAY_HMAC_ENFORCE_ENV, "").strip().lower()
    if raw in _TRUEY:
        return True
    if raw in _FALSEY:
        return False
    # Unset / blank / unrecognized: fail-closed in production, off elsewhere.
    return _is_production()


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
        scopes: Fine-grained permission scopes minted by Core (the JWT
            ``permissions`` claim, e.g. ``["narcotic.vault.read"]``) and carried
            through the gateway's signed context ``scopes`` field. Populated
            ONLY from a VERIFIED signed context — the unsigned/legacy header path
            has no scopes header, so it stays ``[]`` there. Services that gate on
            fine-grained ``require_permission("<scope>")`` read this alongside
            ``roles``; without it every such gate 403s because only role NAMES
            reach the service.
        mfa_verified: Verified MFA evidence carried only from a signed gateway
            context. Unsigned/legacy identity headers never grant MFA status.
        is_demo: True when this request runs inside a Cortex Live public demo
            session. Populated ONLY from a VERIFIED signed gateway context —
            the unsigned/legacy header path always yields ``False``, so no raw
            header (e.g. ``X-Is-Demo``) can ever grant demo status.
        demo_session_id: Cortex Live demo session UUID. Set only when
            ``is_demo`` is true on a verified signed context; ``None`` otherwise.
        demo_lease_id: Demo tenant lease UUID for the leased demo tenant. Set
            only when ``is_demo`` is true on a verified signed context.
        demo_persona: Active demo persona key (e.g. ``agency_admin``). Set only
            when ``is_demo`` is true on a verified signed context.
    """

    user_id: UUID
    tenant_id: UUID
    email: str = ""
    roles: list[str] = []
    is_founder: bool = False
    scopes: list[str] = []
    mfa_verified: bool = False
    is_demo: bool = False
    demo_session_id: UUID | None = None
    demo_lease_id: UUID | None = None
    demo_persona: str | None = None

    model_config = {"frozen": True}


def _is_production() -> bool:
    return os.getenv(_ENV_VAR, "").strip().lower() in ("production", "prod")


def _parse_roles(raw: str | None) -> list[str]:
    """Parse the unsigned/legacy ``X-User-Roles`` header into a role list.

    Forensic audit finding, fixed 2026-07-05 (discovered while wiring
    Adaptix-Imports-Service to this dependency): the gateway's Cognito auth
    middleware (``adaptix-gateway/backend/app/middleware/cognito_auth.py``,
    ``_parse_roles_for_signing``) forwards the raw ``custom:adaptix_roles``
    Cognito claim into the legacy ``X-User-Roles`` header UNCHANGED — Cognito
    stores that claim as a JSON-array string (e.g. ``'["admin","operator"]'``,
    default ``"[]"``), not a comma-delimited string. This function previously
    only comma-split the value, so a real JSON-array header produced a single
    garbage role of literal text (e.g. ``'["admin"]'``) instead of
    ``["admin"]`` on the unsigned/legacy path (reachable whenever the gateway
    HMAC signature is absent or unverifiable — the default outside
    production). Every downstream role/permission check driven by
    ``AuthContext.roles`` on that path silently failed. This now mirrors the
    gateway producer's own ``_parse_roles_for_signing`` convention: JSON-array
    first, comma-delimited fallback for legacy/manually-set values.
    """
    if not raw:
        return []
    stripped = raw.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(r).strip() for r in parsed if str(r).strip()]
        except json.JSONDecodeError:
            pass
    return [r.strip() for r in stripped.split(",") if r.strip()]


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
    x_adaptix_auth_key_id: Annotated[
        str | None, Header(alias="X-Adaptix-Auth-Key-Id")
    ] = None,
    # Injected by FastAPI from the annotation alone (the default is only for
    # direct, non-HTTP callers such as the unit tests). It supplies the
    # actual inbound method/path for the signed method/path binding check;
    # a service that enables ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH fails
    # closed when the request is unavailable. Placed LAST so a caller invoking
    # this dependency positionally (a non-HTTP unit test) cannot bind an
    # unrelated argument to it. The annotation MUST stay the bare ``Request``
    # class: FastAPI recognises the request-injection special case only by
    # ``issubclass`` on the annotation, so ``Request | None`` is treated as a
    # query parameter of type Request and fails app startup in every service
    # that mounts this dependency (proven by
    # test_get_auth_context_mounts_as_fastapi_dependency). The ``None``
    # default is only for direct callers.
    request: Request = cast(Request, None),
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
        x_adaptix_auth_context: Signed gateway context (X-Adaptix-Auth-Context).
        x_adaptix_auth_signature: Its signature (X-Adaptix-Auth-Signature) —
            hex on gateway-v1, base64url on gateway-v2.
        x_adaptix_auth_path: Signing scheme (X-Adaptix-Auth-Path).
        x_adaptix_auth_key_id: ``kid`` of the gateway signing key
            (X-Adaptix-Auth-Key-Id). REQUIRED to verify a gateway-v2 context —
            it selects the public key. Both routing headers are
            attacker-controlled and can only ever select a STRICTER scheme;
            ``verify_gateway_signature`` gates the final choice on this
            service's trust mode, so no header downgrades a verifier.

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
    # This block adds 401s for (a) a present but invalid signature, and
    # (b) an ABSENT signature whenever ``_gateway_hmac_enforce()`` is true.
    #
    # Read that resolver, not this comment, for the default: an unset or
    # blank ADAPTIX_GATEWAY_HMAC_ENFORCE resolves to ``_is_production()``.
    # So in production the absent-signature path is fail-CLOSED by default
    # and a service keeps its unsigned intra-VPC callers only by setting the
    # variable false-y; outside production the default stays off so local
    # development and test suites work without a running gateway. That is
    # the APPSEC-CONTRACTS-UNSIGNED-HEADER-TRUST behaviour described in the
    # module header.
    # ------------------------------------------------------------------
    global _warned_absent_signature, _warned_missing_secret
    # Holds the verified gateway payload when (and only when) a present signature
    # was successfully verified against the configured shared secret. When set,
    # it is the AUTHORITATIVE source for roles / email / founder status — the
    # individually spoofable X-User-Roles / X-Is-Founder / X-User-Email headers
    # are then ignored.
    verified_payload: dict | None = None
    signature_present = has_gateway_signature(
        context_b64=x_adaptix_auth_context,
        signature_hex=x_adaptix_auth_signature,
    )
    secret = gateway_shared_secret()
    # D-053: verification capability is no longer "a shared secret exists".
    # A service in the asymmetric end-state holds ONLY public verification keys
    # — the rollout removes ADAPTIX_GATEWAY_SHARED_SECRET from its task
    # definition. Gating on the secret alone would take every migrated service
    # to the 503 branch below on its first signed request. Scheme selection and
    # trust-mode gating stay inside ``verify_gateway_signature``; this only asks
    # whether there is any material to verify WITH.
    can_verify = secret is not None or has_verification_keys()

    if signature_present:
        if can_verify:
            # Behavior 1: present + secret -> verify. Failure -> 401.
            # ``verify_gateway_signature`` also enforces audience pinning on this
            # verified path when ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` is set
            # (string-equal or list-membership); it is a no-op when unset. That
            # is the only place audience is (or should be) checked — an unsigned
            # request has no trustworthy audience to pin.
            try:
                # Verify ONCE per request. If the module entitlement gate (or any
                # other authentication-dependent check) already verified this
                # exact assertion earlier in the same request, reuse that
                # verified principal instead of re-verifying -- which the
                # single-use replay guard would reject as a false replay. A
                # genuinely separate request has a fresh request scope and
                # verifies independently, so cross-request replay protection is
                # unchanged. The wrapper derives request_method/request_path from
                # the request itself.
                verified = verify_gateway_signature_for_request(
                    request,
                    context_b64=x_adaptix_auth_context or "",
                    signature_hex=x_adaptix_auth_signature or "",
                    shared_secret=secret,
                    auth_path=x_adaptix_auth_path,
                    key_id=x_adaptix_auth_key_id,
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
            # Verification + identity-match succeeded: the signed payload is now
            # the authoritative source for roles / email / founder status.
            verified_payload = verified
        else:
            # Behavior 3: signature present but NO verification material at all
            # — neither a shared secret (gateway-v1) nor public keys
            # (gateway-v2). A signed request that cannot be verified must not be
            # trusted. Production: fail-closed (503 — misconfiguration, not the
            # caller's fault, but we refuse to trust an unverifiable signed
            # context). Non-production: allow as before, warn once (dev
            # ergonomics).
            if _is_production():
                logger.error(
                    "gateway signature present but neither "
                    "ADAPTIX_GATEWAY_SHARED_SECRET nor ADAPTIX_GATEWAY_PUBLIC_KEYS "
                    "is configured in production; refusing to trust an "
                    "unverifiable signed context (fail-closed)."
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Gateway auth context signature present but the service "
                        "has no verification material configured; cannot verify."
                    ),
                )
            if not _warned_missing_secret:
                logger.warning(
                    "gateway signature present but neither "
                    "ADAPTIX_GATEWAY_SHARED_SECRET nor ADAPTIX_GATEWAY_PUBLIC_KEYS "
                    "is configured; cannot verify. Allowing request "
                    "(non-production; configure verification material to enable "
                    "verification)."
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

    if verified_payload is not None:
        # Authoritative path: derive roles / email / founder from the verified
        # signed context. Spoofable X-User-Roles / X-Is-Founder / X-User-Email
        # headers are ignored so an in-VPC actor cannot escalate without a
        # signature over those exact claims.
        signed_roles = verified_payload.get("roles")
        roles = (
            [str(r).strip() for r in signed_roles if str(r).strip()]
            if isinstance(signed_roles, list)
            else []
        )
        email = str(verified_payload.get("email") or "").strip()
        is_founder_flag = bool(verified_payload.get("is_founder")) or (
            "founder" in {r.lower() for r in roles}
        )
        if is_founder_flag and "founder" not in {r.lower() for r in roles}:
            roles = ["founder", *roles]
        # Fine-grained permission scopes from the VERIFIED signed context. The
        # gateway signs the Core-minted ``permissions`` claim into ``scopes``.
        # Case preserved for exact downstream ``require_permission`` matching.
        signed_scopes = verified_payload.get("scopes")
        scopes = (
            [str(s).strip() for s in signed_scopes if str(s).strip()]
            if isinstance(signed_scopes, list)
            else []
        )
        mfa_verified = verified_payload.get("mfa_verified") is True

        # Cortex Live demo context — honoured ONLY from the verified signed
        # payload. A demo context that is present but malformed is REJECTED
        # rather than silently downgraded to an ordinary authenticated context:
        # every downstream demo safety gate (side-effect policy, tenant lease
        # checks, reset scoping) keys off these fields, so "demo token quietly
        # becomes a normal token" would strip those protections while keeping
        # the session alive. A demo principal may also never be founder — the
        # founder role lifts tenant scoping, which is exactly what an isolated
        # leased demo tenant must never escape.
        is_demo = verified_payload.get("is_demo") is True
        demo_session_id: UUID | None = None
        demo_lease_id: UUID | None = None
        demo_persona: str | None = None
        if is_demo:
            raw_demo_session = str(
                verified_payload.get("demo_session_id") or ""
            ).strip()
            raw_demo_lease = str(verified_payload.get("demo_lease_id") or "").strip()
            raw_demo_persona = str(verified_payload.get("demo_persona") or "").strip()
            try:
                demo_session_id = UUID(raw_demo_session)
                demo_lease_id = UUID(raw_demo_lease)
            except (ValueError, AttributeError) as exc:
                logger.warning(
                    "signed demo context has malformed demo_session_id/"
                    "demo_lease_id; rejecting (no silent downgrade)."
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Demo auth context claims are malformed.",
                ) from exc
            if not raw_demo_persona:
                logger.warning("signed demo context has empty demo_persona; rejecting.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Demo auth context claims are malformed.",
                )
            if is_founder_flag:
                logger.warning(
                    "signed demo context claims founder; rejecting "
                    "(demo principals are never founder)."
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Demo auth context may not carry founder privilege.",
                )
            demo_persona = raw_demo_persona
    else:
        # Unsigned / legacy path (no verifiable signature): trust the injected
        # headers exactly as before. Reachable only when the absent-signature
        # path is allowed (enforcement off) or no shared secret is configured.
        # There is no unsigned scopes header, so scopes stay empty on this path.
        # Demo status is NEVER derivable here: only a verified signed context
        # can mark a request as a Cortex Live demo session, so a raw
        # ``X-Is-Demo: true`` (or any other unsigned input) grants nothing.
        roles = _parse_roles(x_user_roles)
        scopes = []
        mfa_verified = False
        is_demo = False
        demo_session_id = None
        demo_lease_id = None
        demo_persona = None
        email = (x_user_email or "").strip()
        is_founder_flag = (x_is_founder or "false").strip().lower() in (
            "true",
            "1",
            "yes",
        )
        # If the X-Is-Founder flag is set, ensure "founder" is in roles.
        if is_founder_flag and "founder" not in {r.lower() for r in roles}:
            roles = ["founder", *roles]
        # Conversely, if "founder" is in roles, set is_founder.
        if "founder" in {r.lower() for r in roles}:
            is_founder_flag = True

        # ------------------------------------------------------------------
        # PRIVILEGE FLOOR — APPSEC-CONTRACTS-UNSIGNED-FOUNDER-ESCALATION.
        #
        # In PRODUCTION, founder is NEVER granted from an unsigned request.
        # Both inputs above (``X-Is-Founder`` and ``X-User-Roles``) are plain
        # request headers covered by no signature, so an in-VPC / ALB-direct
        # caller that reaches a service without traversing the gateway could
        # send ``X-Is-Founder: true`` and be treated as the platform owner —
        # which lifts tenant scoping on founder-gated cross-tenant reads.
        #
        # This REJECTS NOTHING. It only refuses to ELEVATE: the request still
        # proceeds with the caller's ordinary roles. That is what makes it
        # safe to land ahead of the per-service HMAC enforcement rollout —
        # unlike removing this branch or defaulting the enforcement flag to
        # true, which would 401 every not-yet-signing caller fleet-wide.
        #
        # Reachability in production is already narrow: the absent-signature
        # path is fail-closed by default here (``_gateway_hmac_enforce`` ->
        # ``_is_production``), so this floor applies only to services that
        # EXPLICITLY set ``ADAPTIX_GATEWAY_HMAC_ENFORCE=false`` — i.e. exactly
        # the services knowingly running in the degraded mode where the
        # escalation is reachable.
        #
        # Outside production the behaviour is deliberately unchanged, so local
        # development and the fleet's test suites can still simulate a founder
        # with headers alone.
        #
        # Precedent: Adaptix-AI-Service already applies this identical floor in
        # its own ``require_auth`` wrapper (``ai_app/auth.py``). This moves the
        # floor into the canonical dependency so every adopter inherits it
        # instead of each service having to reimplement it.
        # ------------------------------------------------------------------
        if is_founder_flag and _is_production():
            logger.warning(
                "founder privilege refused on an UNSIGNED gateway context "
                "(user=%s tenant=%s roles=%s) — founder is only honoured on an "
                "HMAC-verified context. Sign the request, or set %s=true once "
                "every caller of this service signs.",
                user_uuid,
                tenant_uuid,
                sorted(roles),
                _GATEWAY_HMAC_ENFORCE_ENV,
            )
            roles = [r for r in roles if r.lower() != _FOUNDER_ROLE]
            is_founder_flag = False

    return AuthContext(
        user_id=user_uuid,
        tenant_id=tenant_uuid,
        email=email,
        roles=roles,
        is_founder=is_founder_flag,
        scopes=scopes,
        mfa_verified=mfa_verified,
        is_demo=is_demo,
        demo_session_id=demo_session_id,
        demo_lease_id=demo_lease_id,
        demo_persona=demo_persona,
    )


# ---------------------------------------------------------------------------
# Backward-compatibility shims for code that imported HMAC/RS256 symbols.
# These raise descriptive errors so dependent code fails loudly rather than
# silently at runtime.
# ---------------------------------------------------------------------------

# ``GATEWAY_SHARED_SECRET_ENV`` is imported from ``gateway_signature`` at the top
# of this module and re-exported here via ``__all__``. It is deliberately NOT
# re-declared: the environment-variable NAME now has exactly one definition in
# the package. Two independent literals could drift apart, which would silently
# point signature verification at a different environment variable than the one
# operations actually configures.
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
# Production default: fail-closed (absent signature -> 401) unless this is
# EXPLICITLY set to a false-y value (``false``/``0``/``no``) to opt a service
# with a legitimate unsigned intra-VPC caller out during migration. Outside
# production the default is off (absent signature allowed) for dev/test.
ADAPTIX_GATEWAY_HMAC_ENFORCE_ENV = _GATEWAY_HMAC_ENFORCE_ENV
__all__.append("ADAPTIX_GATEWAY_HMAC_ENFORCE_ENV")
