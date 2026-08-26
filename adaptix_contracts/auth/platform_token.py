"""Canonical Adaptix TENANT-LESS platform service-to-service (S2S) token.

:mod:`adaptix_contracts.auth.service_token` proves a caller's identity for a
call that acts FOR a tenant (``ServiceTokenClaims.tenant_id`` is a required
claim). Some S2S calls are genuinely tenant-less by nature — nothing to bind
to, because no tenant exists yet. The motivating case: Core-Service sending a
pre-signup marketing email via Calendar-Service's internal mail endpoint,
before any agency/workspace/tenant has been created. Today that endpoint
authenticates callers with a bare fleet-wide shared secret held by dozens of
services — that proves only "holder of a widely-distributed secret", not
caller identity, with no expiry and no replay binding.

This module is a SEPARATE, additive primitive for exactly that situation. It
is not an alternative way to skip tenant binding when a tenant DOES exist —
if the call is acting for a tenant/workspace, even indirectly, use
``service_token`` instead. Reaching for this module because tenant plumbing
is inconvenient is a misuse of it.

Why a separate model instead of making ``ServiceTokenClaims.tenant_id``
optional: ``tenant_id`` is relied on as a structural (Pydantic-enforced)
guarantee by tenant-scoped verifiers (Operations -> CAD/Air scene dispatch,
MCP -> EPCR). Making it optional would mean that guarantee holds only for as
long as every verifier's assumptions are re-audited — a verifier that leans
on "the model wouldn't construct without it" would lose that protection
silently, at whatever moment it next re-pins this package, in a change
nobody reviews as a security change. ``PlatformServiceTokenClaims`` instead
has NO ``tenant_id`` field at all — structurally absent, not
present-but-optional and not empty-string — so an existing tenant-scoped
verifier rejects a platform token by construction, and this module's own
verifier rejects a tenant token by construction (see ``token_use`` below).
Safety here is a shape guarantee, not a value someone has to remember to
check.

Signing: identical machinery to ``service_token`` — RS256 with an RSA
private key held only by the issuer, ``kid``-based key rotation, and the
same SSRF-safe local-keyset resolution (see ``_s2s_keyset``). No new crypto
was invented for this module.

Claims (see ``PlatformServiceTokenClaims``): token_use, iss, aud, sub, scope,
jti, iat, nbf, exp, correlation_id, ver. No tenant_id. No secrets and no
patient/clinical data belong in this token, same as ``service_token``.

Discriminator: every platform token carries a REQUIRED ``token_use =
"platform-s2s"`` claim. A tenant-bound ``ServiceTokenClaims`` token never has
this claim, and a platform token never has ``tenant_id``. Neither verifier
can mistake the other's token for its own — proven in
``tests/test_platform_token_tenant_boundary.py``.

Replay resistance: see the docstring on ``verify_platform_service_token``.
By default it is TTL-bounded only, matching the current fleet convention
(``service_token`` itself does not dedupe ``jti``, and neither does
Adaptix-EPCR-Service's ``mcp_s2s.py`` verifier — both rely on
kid+signature+exp/nbf and a short TTL). An optional ``reject_replayed_jti``
hook is available for a caller that needs a duplicate rejected within the
TTL window, e.g. exactly the "send this marketing email once" case that
motivated this module.

Verification maps to HTTP results the same way ``service_token`` does:
``PlatformServiceTokenError`` -> 401 authentication,
``PlatformServiceTokenAuthzError`` -> 403 authorization.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pydantic import BaseModel, Field

from adaptix_contracts.auth._s2s_keyset import ALGORITHM as _SHARED_ALGORITHM
from adaptix_contracts.auth._s2s_keyset import (
    resolve_keyset_signing_key as _resolve_keyset_signing_key,
)

# Current claims schema version. Independent of SERVICE_TOKEN_VERSION — these
# are two separate claims schemas that evolve on their own timelines.
PLATFORM_TOKEN_VERSION = 1

# Required discriminator claim value. See module docstring.
TOKEN_USE = "platform-s2s"

# Default short lifetime — matches service_token's default. A platform token
# is minted per call, not reused past its purpose.
DEFAULT_TTL_SECONDS = 120
# Clock-skew tolerance (matches service_token / the platform's 5s gateway-
# signature leeway).
LEEWAY_SECONDS = 5

# The ONE approved S2S algorithm, defined once in _s2s_keyset and shared with
# adaptix_contracts.auth.service_token. Not a new crypto choice.
_ALGORITHM = _SHARED_ALGORITHM


class PlatformServiceTokenError(ValueError):
    """Authentication failure (map to HTTP 401).

    Raised for missing/invalid/expired/not-yet-valid tokens, unknown signing
    keys, untrusted issuers, and tokens that are not shaped like a platform
    token (missing/incorrect ``token_use`` or ``ver``) — anything that means
    the token cannot be trusted as an authentic platform token.

    Deliberately NOT a subclass of ``ServiceTokenError`` (and vice versa):
    code that catches one must not accidentally also catch the other. Each
    call site must explicitly decide which S2S trust model it is verifying
    against.
    """


class PlatformServiceTokenAuthzError(ValueError):
    """Authorization failure (map to HTTP 403).

    Raised when the token is authentic but not permitted: wrong audience,
    wrong caller service, or missing scope.
    """


class PlatformServiceTokenClaims(BaseModel):
    """Validated claims carried by a canonical Adaptix platform S2S token.

    Deliberately has NO ``tenant_id`` field. See module docstring for why
    that is a structural guarantee rather than a documented convention.
    """

    token_use: Literal["platform-s2s"] = Field(
        ...,
        description=(
            "Required discriminator, always 'platform-s2s'. Exists so a "
            "platform token can never be silently accepted by a "
            "tenant-scoped verifier's claims model, and a tenant-bound "
            "token can never be silently accepted here — both directions "
            "fail closed on token shape, not on a value someone remembered "
            "to check."
        ),
    )
    iss: str = Field(
        ..., description="Canonical Adaptix issuer service, e.g. adaptix-core"
    )
    aud: str = Field(
        ..., description="Exact downstream audience, e.g. adaptix-calendar"
    )
    sub: str = Field(..., description="Calling service identity, e.g. adaptix-core")
    scope: str = Field(..., description="Authorized action, e.g. mail:send-marketing")
    jti: str = Field(
        ...,
        description="Unique token id (replay correlation; see verify_platform_service_token)",
    )
    iat: int = Field(..., description="Issued-at (epoch seconds)")
    exp: int = Field(..., description="Expiration (epoch seconds)")
    nbf: int | None = Field(default=None, description="Not-before (epoch seconds)")
    correlation_id: str | None = Field(
        default=None, description="Cross-service correlation id (audit/tracing)"
    )
    ver: int = Field(
        default=PLATFORM_TOKEN_VERSION, description="Claims schema version"
    )


def issue_platform_service_token(
    *,
    private_key_pem: str,
    issuer: str,
    audience: str,
    subject: str,
    scope: str,
    kid: str | None = None,
    correlation_id: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> str:
    """Mint a signed (RS256) platform token. ``private_key_pem`` never leaves the issuer.

    There is intentionally no ``tenant_id`` parameter — this function cannot
    mint a tenant-bound claim even by caller mistake.

    Raises:
        PlatformServiceTokenError: required identity/scope inputs are missing.
    """
    for name, value in (
        ("issuer", issuer),
        ("audience", audience),
        ("subject", subject),
        ("scope", scope),
    ):
        if not value or not str(value).strip():
            raise PlatformServiceTokenError(
                f"{name} is required to issue a platform service token"
            )

    issued = now or datetime.now(UTC)
    iat = int(issued.timestamp())
    exp = int((issued + timedelta(seconds=max(1, ttl_seconds))).timestamp())
    payload: dict[str, Any] = {
        "token_use": TOKEN_USE,
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "scope": scope,
        "jti": uuid.uuid4().hex,
        "iat": iat,
        "nbf": iat,
        "exp": exp,
        "ver": PLATFORM_TOKEN_VERSION,
    }
    if correlation_id:
        payload["correlation_id"] = correlation_id

    headers = {"kid": kid} if kid else None
    return jwt.encode(payload, private_key_pem, algorithm=_ALGORITHM, headers=headers)


def verify_platform_service_token(
    token: str,
    *,
    public_key_pem: str,
    expected_issuer: str,
    expected_audience: str,
    expected_subject: str,
    required_scope: str,
    leeway_seconds: int = LEEWAY_SECONDS,
    reject_replayed_jti: Callable[[str], bool] | None = None,
) -> PlatformServiceTokenClaims:
    """Verify a platform token and return its validated claims.

    Enforces (in order): signature+exp+nbf+issuer (401 on failure), audience
    (403), platform token_use discriminator (401 — wrong token shape, not
    merely wrong permission), schema version (401), caller subject (403),
    required scope (403). There is no tenant check of any kind — there is no
    tenant claim to check.

    Replay resistance:

    By default (``reject_replayed_jti=None``), replay resistance is
    TTL-bounded ONLY — identical to the current fleet convention. Neither
    ``service_token`` nor Adaptix-EPCR-Service's MCP S2S verifier
    (``mcp_s2s.py``) track ``jti``; both rely on kid + signature +
    exp/nbf + a short TTL. A replayed platform token can be re-accepted
    until it expires (``DEFAULT_TTL_SECONDS`` = 120s by default, entirely
    caller-controlled via ``issue_platform_service_token(ttl_seconds=...)``).
    This is acceptable whenever the downstream effect is naturally
    idempotent, or a duplicate within the TTL window is an acceptable risk.

    For a call where a duplicate within the TTL window is NOT acceptable
    (e.g. a literal "send this email once" action with no downstream
    idempotency key of its own), pass ``reject_replayed_jti``: a callable
    ``(jti: str) -> bool`` that ATOMICALLY checks-and-records the jti in a
    shared, durable store (e.g. Redis ``SET key NX EX <ttl>``, or a
    DynamoDB conditional put keyed on the jti) and returns ``True`` if the
    jti was ALREADY recorded (replay -> reject with
    ``PlatformServiceTokenError``) or ``False`` if this is the first time it
    has been recorded (accept). This is a deliberate strengthening beyond
    the fleet default, opt-in per call site.

    The check-and-record MUST be a single atomic operation. A
    read-then-write callback (e.g. "look the key up, then set it if
    absent") is NOT replay-safe under concurrent requests carrying the same
    token: two concurrent calls can both observe "not seen" before either
    one records it, and both would be accepted. See
    ``test_verify_platform_service_token_concurrent_replay_dedupe_is_race_safe``
    in the test suite for the property an atomic callback buys you, and
    ``test_verify_platform_service_token_naive_non_atomic_dedupe_is_not_race_safe``
    for a demonstration of exactly the race a non-atomic callback fails to
    close. The backing store's retention only needs to cover the token TTL
    — anything past ``exp`` is already rejected by signature verification
    alone, so entries can be evicted once the token they guard has expired.

    Raises:
        PlatformServiceTokenError: authentication failure -> HTTP 401.
        PlatformServiceTokenAuthzError: authorization failure -> HTTP 403.
    """
    if not token or not token.strip():
        raise PlatformServiceTokenError("missing platform service token")

    raw = _decode_platform_jwt(
        token,
        public_key_pem=public_key_pem,
        expected_issuer=expected_issuer,
        expected_audience=expected_audience,
        leeway_seconds=leeway_seconds,
    )
    _check_platform_token_use_and_version(raw)
    _authorize_platform_claims(
        raw, expected_subject=expected_subject, required_scope=required_scope
    )
    _reject_smuggled_tenant_id(raw)
    _check_platform_replay(raw, reject_replayed_jti)

    return PlatformServiceTokenClaims(**raw)


def _decode_platform_jwt(
    token: str,
    *,
    public_key_pem: str,
    expected_issuer: str,
    expected_audience: str,
    leeway_seconds: int,
) -> dict[str, Any]:
    """Decode and cryptographically verify the JWT envelope (signature, exp,
    nbf, iss, aud), translating PyJWT's exception taxonomy into the platform
    token's own. Does not know anything about platform-specific claim shape
    or authorization — see the other ``_check_platform_*`` /
    ``_authorize_platform_*`` helpers below, which ``verify_platform_service_token``
    calls in the same order this module always has.

    ``jti`` is required at decode time (not merely checked later, conditionally,
    by the replay hook): a token missing it would otherwise fail
    ``PlatformServiceTokenClaims`` construction with an unhandled
    ``pydantic.ValidationError`` instead of a clean ``PlatformServiceTokenError``,
    even on the default (no replay hook) path.
    """
    try:
        return jwt.decode(
            token,
            public_key_pem,
            algorithms=[_ALGORITHM],
            audience=expected_audience,
            issuer=expected_issuer,
            leeway=leeway_seconds,
            options={"require": ["exp", "iat", "aud", "iss", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise PlatformServiceTokenError("platform service token expired") from exc
    except jwt.ImmatureSignatureError as exc:
        raise PlatformServiceTokenError("platform service token not yet valid") from exc
    except jwt.InvalidAudienceError as exc:
        # Authentic-but-not-for-this-service -> authorization failure.
        raise PlatformServiceTokenAuthzError(
            "platform service token audience mismatch"
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise PlatformServiceTokenError(
            "platform service token issuer not trusted"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise PlatformServiceTokenError(
            f"invalid platform service token: {type(exc).__name__}"
        ) from exc


def _check_platform_token_use_and_version(raw: dict[str, Any]) -> None:
    """Confirm the decoded payload is actually shaped like a platform token
    (correct discriminator, supported schema version). Authentication-level
    (401) checks: a token failing these is not trustworthy as a platform
    token at all, independent of who it claims to be or what it asks for."""
    if raw.get("token_use") != TOKEN_USE:
        raise PlatformServiceTokenError(
            f"not a platform service token (token_use={raw.get('token_use')!r})"
        )

    ver = raw.get("ver")
    if ver != PLATFORM_TOKEN_VERSION:
        raise PlatformServiceTokenError(
            f"unsupported platform service token version: {ver!r}"
        )


def _authorize_platform_claims(
    raw: dict[str, Any], *, expected_subject: str, required_scope: str
) -> None:
    """Confirm an authentic, correctly-shaped token actually authorizes this
    caller for this action. Permission-level (403) checks."""
    if raw.get("sub") != expected_subject:
        raise PlatformServiceTokenAuthzError(
            "platform service token caller subject not authorized"
        )

    if raw.get("scope") != required_scope:
        raise PlatformServiceTokenAuthzError(
            f"platform service token missing required scope {required_scope!r}"
        )


def _reject_smuggled_tenant_id(raw: dict[str, Any]) -> None:
    """Defense in depth: a conforming issuer never sets ``tenant_id`` (see
    ``issue_platform_service_token``, which has no ``tenant_id`` parameter),
    so this only fires for a hand-crafted or buggy payload. Refuse rather
    than silently drop it via ``PlatformServiceTokenClaims`` construction —
    never let a token that looks like it might carry tenant trust pass
    through this verifier under any interpretation."""
    if "tenant_id" in raw:
        raise PlatformServiceTokenError(
            "platform service token must not carry a tenant_id claim"
        )


def _check_platform_replay(
    raw: dict[str, Any], reject_replayed_jti: Callable[[str], bool] | None
) -> None:
    """Enforce the optional replay-dedupe hook. See the docstring on
    ``verify_platform_service_token`` for the atomicity requirement this
    depends on when a caller opts in."""
    if reject_replayed_jti is None:
        return
    jti = raw.get("jti")
    if not jti or not str(jti).strip():
        raise PlatformServiceTokenError(
            "platform service token missing jti (required for replay check)"
        )
    if reject_replayed_jti(str(jti)):
        raise PlatformServiceTokenError(
            "platform service token jti already used (replay rejected)"
        )


def verify_platform_service_token_with_keyset(
    token: str,
    *,
    trusted_keys: dict[str, str],
    expected_issuer: str,
    expected_audience: str,
    expected_subject: str,
    required_scope: str,
    leeway_seconds: int = LEEWAY_SECONDS,
    reject_replayed_jti: Callable[[str], bool] | None = None,
) -> PlatformServiceTokenClaims:
    """Verify a platform token against a trusted ``{kid: public_key_pem}`` keyset.

    Canonical downstream verifier (e.g. Calendar-Service's internal mail
    endpoint). Uses the identical unforgeable, SSRF-safe key-selection
    algorithm as ``service_token.verify_service_token_with_keyset`` (shared
    via ``_s2s_keyset``) — a caller can never influence which key validates
    a token, and the verifier never tries every key until one happens to
    pass:

    - header ``alg`` MUST be the approved algorithm (RS256), else 401;
    - header MUST carry a non-empty ``kid``, else 401 (KID_MISSING);
    - ``kid`` MUST resolve to exactly one key in the LOCAL ``trusted_keys``
      map, else 401 (KID_UNKNOWN). Keys are supplied by the service (active
      + previous during rotation) and NEVER fetched from a token-controlled
      URL (no jku/x5u/JWKS-by-URL) — SSRF-safe by construction;
    - the resolved key then runs full claim verification via
      ``verify_platform_service_token`` (see that function's docstring for
      the token_use/tenant_id/replay behavior).

    Raises ``PlatformServiceTokenError`` (-> 401) for missing/unknown key,
    wrong algorithm, malformed/bad-signature/expired/untrusted-issuer/wrong
    token shape/replay; ``PlatformServiceTokenAuthzError`` (-> 403) for
    audience/subject/scope failures.
    """
    public_key = _resolve_keyset_signing_key(
        token,
        trusted_keys=trusted_keys,
        algorithm=_ALGORITHM,
        code_prefix="PLATFORM_TOKEN",
        error_type=PlatformServiceTokenError,
    )
    return verify_platform_service_token(
        token,
        public_key_pem=public_key,
        expected_issuer=expected_issuer,
        expected_audience=expected_audience,
        expected_subject=expected_subject,
        required_scope=required_scope,
        leeway_seconds=leeway_seconds,
        reject_replayed_jti=reject_replayed_jti,
    )
