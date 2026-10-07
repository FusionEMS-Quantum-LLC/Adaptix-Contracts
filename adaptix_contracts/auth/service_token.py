"""Canonical Adaptix service-to-service (S2S) identity token.

The shared ``INTERNAL_SERVICE_KEY`` proves only that *a* trusted process holds a
shared secret. It does not prove which service is calling, which tenant it is
acting for, which user initiated the request, or which operation is authorized —
and a valid-looking body ``tenant_id`` is not authorization evidence.

This module defines the ONE canonical, cryptographically-signed, short-lived,
tenant-bound service token used for Operations -> CAD / Air scene dispatch (and
future S2S calls). It extends the platform's existing asymmetric JWT pattern
(Core signs user JWTs with an RSA private key; services verify with the public
key) — it does NOT introduce a new broadly-shared HMAC secret.

Signing:  RS256 with an RSA private key held only by the issuer (Operations),
          via the approved secret/KMS mechanism. Verifiers (CAD/Air) hold only
          the public key. ``kid`` supports rotation (verifiers accept the active
          and previous key).

Claims (see ``ServiceTokenClaims``): iss, aud, sub, tenant_id, scope, jti, iat,
nbf, exp, actor_sub, correlation_id, scene_request_id, workspace_key,
delegation_grant_id, tool_call_id, actor_mfa_verified_at, ver. No secrets and no
patient/clinical data belong in the token.

``actor_mfa_verified_at`` (optional, 5.30.0) is identity assurance only: the
epoch second at which the issuer itself observed, in a gateway-signed and
verified request context for the same ``actor_sub``, that the actor held a
fresh second factor. The gateway context cannot be relayed (it is audience-,
method- and path-bound, single-use and short-lived), so this signed claim is
how an issuer such as ePCR carries that fact to a receiver such as Narcotics.
Receivers decide freshness with the one canonical check,
``require_fresh_actor_mfa_assurance``.

Verification maps to HTTP results (``ServiceTokenError`` -> 401 authentication,
``ServiceTokenAuthzError`` -> 403 authorization) so downstream services enforce:
missing/invalid/expired/unknown-key/untrusted-issuer/malformed
actor_mfa_verified_at -> 401; wrong audience / wrong caller service / missing
scope / missing-or-mismatched tenant -> 403. A missing, stale or future actor MFA
assurance is ``ServiceTokenMfaAssuranceError`` (a ``ServiceTokenAuthzError``,
so 403) with a machine-readable ``reason``.

A verifier names the audience(s) it accepts as ``expected_audience``: one
string, or (5.35.0) a non-empty sequence of strings for a receiver whose
audience is being renamed. During such a cutover the receiver accepts both its
new audience and the legacy one, so the issuer can switch in its own deploy
with no window in which every token is refused; the receiver drops the legacy
value once the issuer has moved. An empty sequence is a programming error and
is refused (``ValueError``) before any token is decoded: it must never read as
"accept nothing" at runtime, and even less as "accept anything".
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, TypeGuard

import jwt
from pydantic import BaseModel, Field

from adaptix_contracts._json_narrowing import is_object_sequence
from adaptix_contracts.auth._s2s_keyset import ALGORITHM as _SHARED_ALGORITHM
from adaptix_contracts.auth._s2s_keyset import (
    resolve_keyset_signing_key as _resolve_keyset_signing_key,
)
from adaptix_contracts.gateway_signature import require_int_seconds

# Current claims schema version. Verifiers reject unknown major versions.
SERVICE_TOKEN_VERSION = 1

# Default short lifetime — a service token is minted per dispatch, not reused.
DEFAULT_TTL_SECONDS = 120
# Clock-skew tolerance (matches the platform's 5s gateway-signature leeway).
LEEWAY_SECONDS = 5

# The ONE approved S2S algorithm, defined once in _s2s_keyset and shared with
# adaptix_contracts.auth.platform_token. Kept as a module-local alias (same
# value, "RS256") so every existing reference to `_ALGORITHM` below is
# unchanged — this is a source-of-definition move, not a behavior change.
_ALGORITHM = _SHARED_ALGORITHM


def _is_epoch_second(value: object) -> TypeGuard[int]:
    """True for an ``int`` that is not a ``bool``: ``True`` is never epoch second 1.

    Over ``object`` so it also holds for what the annotations cannot constrain:
    a claim read out of a decoded token, an untyped caller, or a claims model
    built with ``model_construct`` (which skips validation). The one rule for
    every ``actor_mfa_verified_at`` check in this module.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def _require_accepted_audiences(expected_audience: object) -> tuple[str, ...]:
    """Normalise ``expected_audience`` to the non-empty tuple PyJWT compares against.

    Called by both verifiers before the token is decoded, in the same place and
    the same spirit as ``require_int_seconds``: a bad bound is a programming
    error in the verifier, not an authentication failure of the token, so it is
    ``ValueError`` and never a 401/403.

    ``str`` is checked first because a ``str`` is itself a ``Sequence[str]`` of
    its characters: ``"adaptix-cad"`` must mean the one audience
    ``adaptix-cad``, never the twelve one-letter audiences PyJWT would otherwise
    accept. PyJWT (``>=2.8``; locked 2.15.0) accepts ``str | Iterable[str]`` for
    ``audience`` and, in its default non-strict mode, passes a token whose
    ``aud`` claim is any member of the iterable; an empty iterable makes it
    refuse every token (``all(...)`` over nothing), which is fail-closed but
    silent, so it is refused here, loudly, before decoding.

    Args:
        expected_audience: One audience string, or a non-empty sequence of
            them (a cutover receiver accepting its new and its legacy audience).

    Raises:
        ValueError: ``expected_audience`` is empty or blank, is neither a
            ``str`` nor a sequence (a set, a generator, bytes, None, an int),
            or contains an element that is not a non-blank ``str``.
    """
    if isinstance(expected_audience, str):
        if not expected_audience.strip():
            raise ValueError("expected_audience must not be blank")
        return (expected_audience,)
    if isinstance(expected_audience, (bytes, bytearray)) or not is_object_sequence(
        expected_audience
    ):
        raise ValueError(
            "expected_audience must be a str or a sequence of str, got "
            f"{type(expected_audience).__name__}"
        )
    entries = tuple(expected_audience)
    if not entries:
        raise ValueError("expected_audience must name at least one audience")
    accepted: list[str] = []
    for audience in entries:
        if not isinstance(audience, str) or not audience.strip():
            raise ValueError(
                "every expected_audience entry must be a non-blank str, got "
                f"{audience!r}"
            )
        accepted.append(audience)
    return tuple(accepted)


class ServiceTokenError(ValueError):
    """Authentication failure (map to HTTP 401).

    Raised for missing/invalid/expired/not-yet-valid tokens, unknown signing
    keys, and untrusted issuers — anything that means the token cannot be
    trusted as authentic.
    """


class ServiceTokenAuthzError(ValueError):
    """Authorization failure (map to HTTP 403).

    Raised when the token is authentic but not permitted: wrong audience, wrong
    caller service, missing scope, or missing/mismatched tenant.
    """


#: Stable machine-readable reasons ``require_fresh_actor_mfa_assurance`` refuses
#: with. Receivers put the reason in their 403 body; it carries no PHI.
ActorMfaAssuranceReason = Literal[
    "actor_mfa_assurance_missing",
    "actor_mfa_assurance_stale",
    "actor_mfa_assurance_in_future",
]


class ServiceTokenMfaAssuranceError(ServiceTokenAuthzError):
    """Actor MFA assurance refused (map to HTTP 403, like its parent).

    A subclass of ``ServiceTokenAuthzError``, so every handler that already maps
    that class to 403 keeps doing so. ``reason`` is one of
    ``ActorMfaAssuranceReason``; the message starts with it. ``detail`` is a
    human-readable explanation with no token or patient data.
    """

    def __init__(self, reason: ActorMfaAssuranceReason, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason: ActorMfaAssuranceReason = reason
        self.detail = detail

    def __reduce__(
        self,
    ) -> tuple[
        type[ServiceTokenMfaAssuranceError], tuple[ActorMfaAssuranceReason, str]
    ]:
        # The default BaseException reduction re-calls the class with
        # ``self.args`` (the formatted message alone), which does not match
        # this two-argument constructor; rebuild from the real fields instead.
        return (type(self), (self.reason, self.detail))


class ServiceTokenClaims(BaseModel):
    """Validated claims carried by a canonical Adaptix service token."""

    iss: str = Field(
        ..., description="Canonical Adaptix issuer service, e.g. adaptix-operations"
    )
    aud: str = Field(
        ..., description="Exact downstream audience, e.g. adaptix-cad / adaptix-air"
    )
    sub: str = Field(
        ..., description="Calling service identity, e.g. adaptix-operations"
    )
    tenant_id: str = Field(
        ..., description="Trusted tenant/workspace the call acts for"
    )
    scope: str = Field(..., description="Authorized action, e.g. scene-dispatch:create")
    jti: str = Field(
        ..., description="Unique token id (replay/idempotency correlation)"
    )
    iat: int = Field(..., description="Issued-at (epoch seconds)")
    exp: int = Field(..., description="Expiration (epoch seconds)")
    nbf: int | None = Field(default=None, description="Not-before (epoch seconds)")
    actor_sub: str | None = Field(
        default=None, description="Initiating user id (for audit)"
    )
    correlation_id: str | None = Field(
        default=None, description="Cross-service correlation id"
    )
    scene_request_id: str | None = Field(
        default=None, description="Bound source scene-request id"
    )
    # --- Additive AI & Agent Connection claims (v1, optional; never required) ---
    # Added for the MCP Tool Broker -> downstream S2S path. These are identity
    # and authorization metadata ONLY. No patient name/DOB/MRN/SSN, no claim
    # details, no medical data, no prompt content, and no tool payload may ever
    # be placed in a service token. Older tokens without these claims remain
    # valid — this does not change the core RS256 trust model or bump the
    # required schema version.
    workspace_key: str | None = Field(
        default=None,
        description="Canonical validated workspace key the call is scoped to",
    )
    delegation_grant_id: str | None = Field(
        default=None,
        description="External connection grant id the call acts under (audit)",
    )
    tool_call_id: str | None = Field(
        default=None, description="Correlation id of the originating MCP tool call"
    )
    # --- Additive actor MFA assurance claim (v1, optional; never required) ---
    # Added for the ePCR -> Narcotics DEA chart hand-off (defect D6), where the
    # receiver must enforce its DEA MFA rule for the initiating clinician. This
    # is identity assurance ONLY: an epoch second, never a factor type, device,
    # phone number, code, secret, prompt or any patient/clinical data. The
    # issuer sets it only together with ``actor_sub`` and never later than the
    # token's own issued-at (plus clock-skew leeway). Freshness is decided by
    # the receiver with ``require_fresh_actor_mfa_assurance``, not here. Older
    # tokens without it remain valid, receivers on older Contracts pins ignore
    # it (the default model config ignores unknown claims), and the required
    # schema version is unchanged. ``strict`` keeps a JSON bool, float or
    # string from being coerced into an epoch second.
    actor_mfa_verified_at: int | None = Field(
        default=None,
        strict=True,
        gt=0,
        description=(
            "Epoch seconds at which the ISSUER observed, in a gateway-signed and"
            " verified request context for this actor_sub, that the actor held a"
            " fresh second factor. Identity assurance only; set only together"
            " with actor_sub."
        ),
    )
    ver: int = Field(default=SERVICE_TOKEN_VERSION, description="Claims schema version")


def issue_service_token(
    *,
    private_key_pem: str,
    issuer: str,
    audience: str,
    subject: str,
    tenant_id: str,
    scope: str,
    kid: str | None = None,
    actor_sub: str | None = None,
    correlation_id: str | None = None,
    scene_request_id: str | None = None,
    workspace_key: str | None = None,
    delegation_grant_id: str | None = None,
    tool_call_id: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
    actor_mfa_verified_at: int | None = None,
) -> str:
    """Mint a signed (RS256) service token. ``private_key_pem`` never leaves the issuer.

    ``actor_mfa_verified_at`` is emitted only when supplied. Supply it only when
    this issuer has itself verified, in a gateway-signed request context for the
    same ``actor_sub``, that the actor held a fresh second factor; pass the epoch
    second of that observation.

    Raises:
        ServiceTokenError: required identity/tenant/scope inputs are missing, or
            ``actor_mfa_verified_at`` is not a positive int epoch second (a bool
            is refused), is later than issued-at plus ``LEEWAY_SECONDS``, or is
            given without a non-empty ``actor_sub``.
    """
    for name, value in (
        ("issuer", issuer),
        ("audience", audience),
        ("subject", subject),
        ("tenant_id", tenant_id),
        ("scope", scope),
    ):
        if not value or not str(value).strip():
            raise ServiceTokenError(f"{name} is required to issue a service token")

    issued = now or datetime.now(UTC)
    iat = int(issued.timestamp())
    exp = int((issued + timedelta(seconds=max(1, ttl_seconds))).timestamp())

    if actor_mfa_verified_at is not None:
        # ``bool`` is an ``int`` subclass: True must never read as epoch second 1.
        # The isinstance checks also stand for untyped callers handing over a
        # float or string lifted out of a JSON context.
        if not _is_epoch_second(actor_mfa_verified_at):
            raise ServiceTokenError(
                "actor_mfa_verified_at must be an int epoch second, got "
                f"{type(actor_mfa_verified_at).__name__}"
            )
        if actor_mfa_verified_at <= 0:
            raise ServiceTokenError(
                "actor_mfa_verified_at must be a positive epoch second"
            )
        if not actor_sub or not actor_sub.strip():
            raise ServiceTokenError(
                "actor_mfa_verified_at requires the actor_sub it was observed for"
            )
        if actor_mfa_verified_at > iat + LEEWAY_SECONDS:
            raise ServiceTokenError(
                "actor_mfa_verified_at is later than the token's issued-at"
            )

    payload: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "tenant_id": tenant_id,
        "scope": scope,
        "jti": uuid.uuid4().hex,
        "iat": iat,
        "nbf": iat,
        "exp": exp,
        "ver": SERVICE_TOKEN_VERSION,
    }
    if actor_sub:
        payload["actor_sub"] = actor_sub
    if correlation_id:
        payload["correlation_id"] = correlation_id
    if scene_request_id:
        payload["scene_request_id"] = scene_request_id
    if workspace_key:
        payload["workspace_key"] = workspace_key
    if delegation_grant_id:
        payload["delegation_grant_id"] = delegation_grant_id
    if tool_call_id:
        payload["tool_call_id"] = tool_call_id
    if actor_mfa_verified_at is not None:
        payload["actor_mfa_verified_at"] = actor_mfa_verified_at

    headers = {"kid": kid} if kid else None
    return jwt.encode(payload, private_key_pem, algorithm=_ALGORITHM, headers=headers)


def verify_service_token(
    token: str,
    *,
    public_key_pem: str,
    expected_issuer: str,
    expected_audience: str | Sequence[str],
    expected_subject: str,
    required_scope: str,
    expected_tenant_id: str | None = None,
    leeway_seconds: int = LEEWAY_SECONDS,
) -> ServiceTokenClaims:
    """Verify a service token and return its validated claims.

    Enforces (in order): signature+exp+nbf+issuer (401 on failure), audience
    (403), caller subject (403), required scope (403), tenant presence and — when
    ``expected_tenant_id`` is supplied (e.g. the request-body tenant) — that the
    signed tenant matches it (403). The caller is still responsible for proving
    the *source scene request* belongs to the signed tenant.

    ``expected_audience`` is the one audience this receiver is, or (5.35.0) a
    non-empty sequence of audiences it accepts while its audience is being
    renamed: the token's ``aud`` must equal one of them, else 403. Keep the
    sequence to the new value plus the legacy one, and drop the legacy value
    once every issuer has moved.

    A present ``actor_mfa_verified_at`` must be a positive int epoch second
    (401 otherwise). Its freshness is NOT judged here; a receiver that needs
    actor MFA calls ``require_fresh_actor_mfa_assurance`` on the result.

    Raises:
        ServiceTokenError: authentication failure -> HTTP 401.
        ServiceTokenAuthzError: authorization failure -> HTTP 403.
        ValueError: ``leeway_seconds`` is a bool, not an int (``inf`` and
            ``nan`` included), or negative; or ``expected_audience`` is blank,
            an empty sequence, not a ``str``/sequence of ``str``, or holds a
            blank or non-``str`` entry. Raised before the token is decoded: a
            programming error, not an authentication failure. PyJWT compares
            ``exp`` against the current time minus the leeway, so an ``inf``
            or ``nan`` leeway would accept a token that expired at any time;
            an empty audience sequence would silently refuse every token.
    """
    require_int_seconds(leeway_seconds, "leeway_seconds")
    accepted_audiences = _require_accepted_audiences(expected_audience)
    if not token or not token.strip():
        raise ServiceTokenError("missing service token")

    try:
        # ``jti`` is required at decode time, not merely declared required on
        # ``ServiceTokenClaims``. Without it here, a validly signed token that
        # omits ``jti`` passes every explicit check below and only fails at the
        # closing ``ServiceTokenClaims(**raw)``, raising ``pydantic.Validation
        # Error`` — which is outside this module's documented contract, so a
        # caller correctly catching only ServiceTokenError/ServiceTokenAuthzError
        # sees an unhandled 500 instead of a clean 401. Matches the same
        # requirement in the sibling ``platform_token`` verifier.
        #
        # ``scope`` is deliberately NOT required here: a missing scope must stay
        # an authorization failure (403) via the explicit comparison below, not
        # become an authentication failure (401).
        raw: dict[str, Any] = jwt.decode(
            token,
            public_key_pem,
            algorithms=[_ALGORITHM],
            audience=accepted_audiences,
            issuer=expected_issuer,
            leeway=leeway_seconds,
            options={"require": ["exp", "iat", "aud", "iss", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ServiceTokenError("service token expired") from exc
    except jwt.ImmatureSignatureError as exc:
        raise ServiceTokenError("service token not yet valid") from exc
    except jwt.InvalidAudienceError as exc:
        # Authentic-but-not-for-this-service -> authorization failure.
        raise ServiceTokenAuthzError("service token audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        raise ServiceTokenError("service token issuer not trusted") from exc
    except jwt.InvalidTokenError as exc:
        # Bad signature, malformed, missing required claim, unknown key, etc.
        raise ServiceTokenError(f"invalid service token: {type(exc).__name__}") from exc

    ver = raw.get("ver")
    if ver != SERVICE_TOKEN_VERSION:
        raise ServiceTokenError(f"unsupported service token version: {ver!r}")

    # ``actor_mfa_verified_at`` is checked here, before the closing
    # ``ServiceTokenClaims(**raw)``, for the same reason ``jti`` is required at
    # decode time: a signed token carrying a bool, float, string, list, object
    # or non-positive number would otherwise fail inside that model (strict
    # int, gt=0) and escape as ``pydantic.ValidationError`` instead of a clean
    # 401. This mirrors the field exactly; JSON null reads as absent, as the
    # model does.
    mfa_verified_at = raw.get("actor_mfa_verified_at")
    if mfa_verified_at is not None and (
        not _is_epoch_second(mfa_verified_at) or mfa_verified_at <= 0
    ):
        raise ServiceTokenError(
            "service token actor_mfa_verified_at claim is not a positive int epoch second"
        )

    if raw.get("sub") != expected_subject:
        raise ServiceTokenAuthzError("service token caller subject not authorized")

    if raw.get("scope") != required_scope:
        raise ServiceTokenAuthzError(
            f"service token missing required scope {required_scope!r}"
        )

    tenant_id = raw.get("tenant_id")
    if not tenant_id or not str(tenant_id).strip():
        raise ServiceTokenAuthzError("service token missing tenant claim")

    if expected_tenant_id is not None and tenant_id != expected_tenant_id:
        raise ServiceTokenAuthzError(
            "service token tenant does not match request tenant"
        )

    return ServiceTokenClaims(**raw)


def verify_service_token_with_keyset(
    token: str,
    *,
    trusted_keys: dict[str, str],
    expected_issuer: str,
    expected_audience: str | Sequence[str],
    expected_subject: str,
    required_scope: str,
    expected_tenant_id: str | None = None,
    leeway_seconds: int = LEEWAY_SECONDS,
) -> ServiceTokenClaims:
    """Verify a service token against a trusted ``{kid: public_key_pem}`` keyset.

    Canonical downstream (CAD/Air) verifier. Enforces an unforgeable, required key
    selection so a caller can never influence which key validates a token, and the
    verifier never tries every key until one happens to pass:

    - header ``alg`` MUST be the approved algorithm (RS256), else 401;
    - header MUST carry a non-empty ``kid``, else 401 (KID_MISSING);
    - ``kid`` MUST resolve to exactly one key in the LOCAL ``trusted_keys`` map,
      else 401 (KID_UNKNOWN). Keys are supplied by the service (active + previous
      during rotation) and NEVER fetched from a token-controlled URL (no
      jku/x5u/JWKS-by-URL) — SSRF-safe by construction;
    - the resolved key then runs full claim verification via ``verify_service_token``.

    ``expected_audience`` is one audience string or (5.35.0) a non-empty
    sequence of accepted audiences, exactly as for ``verify_service_token``.

    Raises ``ServiceTokenError`` (-> 401) for missing/unknown key, wrong algorithm,
    malformed/bad-signature/expired/untrusted-issuer, or a malformed
    ``actor_mfa_verified_at``; ``ServiceTokenAuthzError`` (-> 403) for
    audience/subject/scope/tenant failures; ``ValueError`` for a
    ``leeway_seconds`` that is a bool, not an int or negative, or an
    ``expected_audience`` that is blank, empty or not made of ``str``, before
    the key is resolved (see ``verify_service_token``).
    """
    require_int_seconds(leeway_seconds, "leeway_seconds")
    _require_accepted_audiences(expected_audience)
    public_key = _resolve_keyset_signing_key(
        token,
        trusted_keys=trusted_keys,
        algorithm=_ALGORITHM,
        code_prefix="SERVICE_TOKEN",
        error_type=ServiceTokenError,
    )
    return verify_service_token(
        token,
        public_key_pem=public_key,
        expected_issuer=expected_issuer,
        expected_audience=expected_audience,
        expected_subject=expected_subject,
        required_scope=required_scope,
        expected_tenant_id=expected_tenant_id,
        leeway_seconds=leeway_seconds,
    )


def require_fresh_actor_mfa_assurance(
    claims: ServiceTokenClaims,
    *,
    max_age_seconds: int,
    now: datetime | None = None,
    leeway_seconds: int = LEEWAY_SECONDS,
) -> int:
    """Return the verified ``actor_mfa_verified_at`` if it is fresh, else refuse (403).

    The ONE canonical freshness check for the actor MFA assurance claim. Call it
    on claims returned by ``verify_service_token`` or
    ``verify_service_token_with_keyset`` wherever a route requires the
    initiating actor's second factor (for example Narcotics' DEA chart routes).

    With ``now_ts`` the whole epoch second of ``now`` (default: the current UTC
    time) and ``value`` the claim:

    - refused as ``actor_mfa_assurance_missing`` when the claim is absent (or
      not an int, which only a caller mutating the model without validation
      can produce) or ``claims.actor_sub`` is empty: an assurance about nobody
      is no assurance;
    - refused as ``actor_mfa_assurance_in_future`` when
      ``value - now_ts > leeway_seconds``;
    - refused as ``actor_mfa_assurance_stale`` when
      ``now_ts - value > max_age_seconds``, so an age of exactly
      ``max_age_seconds`` passes and one second more does not.

    Raises:
        ServiceTokenMfaAssuranceError: the assurance is missing, stale or in the
            future (a ``ServiceTokenAuthzError`` -> HTTP 403); ``reason`` carries
            the machine-readable cause.
        ValueError: programming error in the call itself. ``max_age_seconds``
            and ``leeway_seconds`` must each be an ``int``: a bool or any
            non-int (a float, including ``inf`` and ``nan``, a str, None) is
            refused before any claim is judged, because ``inf`` and ``nan``
            would make every freshness comparison false. ``max_age_seconds``
            must then be positive and ``leeway_seconds`` non-negative, so no
            configuration value can switch the check off; ``now`` must be
            timezone-aware, because a naive datetime is read as host-local time
            and would shift the decision by the host's UTC offset.
    """
    # The one shared bound rule (type before range; see require_int_seconds):
    # ``inf`` and ``nan`` would make every freshness comparison false, which
    # fails open, and True must not read as one second.
    require_int_seconds(max_age_seconds, "max_age_seconds", positive=True)
    require_int_seconds(leeway_seconds, "leeway_seconds")
    if now is not None and now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")

    verified_at = claims.actor_mfa_verified_at
    actor_sub = claims.actor_sub
    if (
        verified_at is None
        or not _is_epoch_second(verified_at)
        or not actor_sub
        or not actor_sub.strip()
    ):
        raise ServiceTokenMfaAssuranceError(
            "actor_mfa_assurance_missing",
            "the service token carries no actor MFA assurance for an identified actor",
        )

    now_ts = int((now or datetime.now(UTC)).timestamp())
    if verified_at - now_ts > leeway_seconds:
        raise ServiceTokenMfaAssuranceError(
            "actor_mfa_assurance_in_future",
            "the actor MFA assurance is later than the current time plus leeway",
        )
    if now_ts - verified_at > max_age_seconds:
        raise ServiceTokenMfaAssuranceError(
            "actor_mfa_assurance_stale",
            f"the actor MFA assurance is older than {max_age_seconds} seconds",
        )
    return verified_at
