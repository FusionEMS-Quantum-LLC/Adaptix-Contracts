"""INTERNAL. Shared RS256 keyset-resolution algorithm for Adaptix S2S tokens.

Not part of the public API of ``adaptix_contracts`` — nothing outside this
package's ``auth`` subpackage should import a leading-underscore module, and
``adaptix_contracts/auth/__init__.py`` does not re-export anything from here.
See that file for the actual public surface.

Both :mod:`adaptix_contracts.auth.service_token` (tenant-bound) and
:mod:`adaptix_contracts.auth.platform_token` (tenant-less) verify a signed
S2S token against a LOCAL ``{kid: public_key_pem}`` map using the identical
unforgeable, SSRF-safe key-selection algorithm:

1. reject an empty/missing token or an empty trusted-keys map;
2. parse the JWT header WITHOUT verifying the signature (cheap, and the only
   way to learn which key to try);
3. pin the header ``alg`` to the one approved algorithm — rejects algorithm
   confusion (e.g. a caller presenting an HS256 token signed with a public
   key used as an HMAC secret);
4. require a non-empty ``kid`` header claim;
5. resolve ``kid`` against the caller-supplied LOCAL map ONLY — never a
   token-controlled URL (no ``jku``/``x5u``/JWKS-by-URL), so a token can
   never tell the verifier which key to trust it with;
6. hand back exactly the one resolved key. The verifier never iterates the
   keyset trying every key until one happens to validate.

Extracting this once means both S2S verifiers share one hardening surface —
a future fix here (e.g. rejecting a new confusable algorithm) applies to
every S2S verifier at once instead of drifting between hand-maintained
copies. This module contains no cryptographic primitives of its own; it only
looks at the (unverified) header and does a dict lookup. The actual
signature/claims verification happens in each caller's own
``jwt.decode(...)`` call.
"""

from __future__ import annotations

import jwt

# The ONE approved algorithm for Adaptix S2S tokens. Both service_token.py
# and platform_token.py import this rather than each hardcoding "RS256", so
# there is exactly one place that defines it.
ALGORITHM = "RS256"


def resolve_keyset_signing_key(
    token: str,
    *,
    trusted_keys: dict[str, str],
    algorithm: str,
    code_prefix: str,
    error_type: type[Exception],
) -> str:
    """Return the trusted public-key PEM selected for ``token``, or raise.

    ``error_type`` is raised with a code built as ``f"{code_prefix}_<REASON>"``
    so each caller module owns its own error-code namespace (e.g.
    ``SERVICE_TOKEN_KID_UNKNOWN`` vs ``PLATFORM_TOKEN_KID_UNKNOWN``) — a
    platform-token failure can never be mistaken for a service-token failure
    by anything pattern-matching on these codes (logs, alerts, dashboards).

    Codes raised, in order checked: ``{prefix}_MISSING``,
    ``{prefix}_KEYSET_EMPTY``, ``{prefix}_MALFORMED``,
    ``{prefix}_ALGORITHM_REJECTED: <alg>``, ``{prefix}_KID_MISSING``,
    ``{prefix}_KID_UNKNOWN``.
    """
    if not token or not token.strip():
        raise error_type(f"{code_prefix}_MISSING")
    if not trusted_keys:
        raise error_type(f"{code_prefix}_KEYSET_EMPTY")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise error_type(f"{code_prefix}_MALFORMED") from exc

    alg = header.get("alg")
    if alg != algorithm:
        raise error_type(f"{code_prefix}_ALGORITHM_REJECTED: {alg!r}")

    kid = header.get("kid")
    if not kid or not str(kid).strip():
        raise error_type(f"{code_prefix}_KID_MISSING")

    public_key = trusted_keys.get(str(kid))
    if not public_key:
        raise error_type(f"{code_prefix}_KID_UNKNOWN")

    return public_key
