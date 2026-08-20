"""Gateway issuer key material — the asymmetric trust store for auth contexts.

Why this module exists (D-053)
------------------------------
Until now the gateway and every domain service shared ONE symmetric secret,
``ADAPTIX_GATEWAY_SHARED_SECRET``, injected fleet-wide from Secrets Manager. A
verifier could therefore prove only that a context came from *a holder of that
secret* — never that it came from *the gateway*. Because ~52 services hold the
same value, compromise of any single service yielded the ability to mint an
arbitrary context (including ``is_founder=true``) that every other service
accepts. That is an issuer/verifier boundary that does not exist.

The replacement implemented here:

* The gateway holds an **Ed25519 private key** that nothing else in the fleet
  has (``ADAPTIX_GATEWAY_SIGNING_PRIVATE_KEY`` + ``..._SIGNING_KEY_ID``).
* Domain services hold **only public verification keys**
  (``ADAPTIX_GATEWAY_PUBLIC_KEYS``, a JWKS document).
* Compromise of a verifier yields zero capability to forge a context accepted
  by another verifier, because a verifier never holds signing material.

Rotation
--------
``ADAPTIX_GATEWAY_PUBLIC_KEYS`` is a JWKS with one entry per key, each carrying
a ``kid``. The gateway stamps the ``kid`` it signed with into
``X-Adaptix-Auth-Key-Id`` and the verifier selects by that ``kid``. Publishing
the *next* public key to every service before the gateway starts using it, and
retaining the *previous* one for one deploy cycle after, makes rotation a
non-event: at any moment the keyset legitimately holds active + previous.

Key format
----------
JWKS entries use RFC 8037 OKP form::

    {"keys": [
      {"kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig",
       "kid": "gw-2026-08", "x": "<base64url raw 32-byte public key>"}
    ]}

Ed25519 is chosen deliberately over RSA/ECDSA: no curve/padding/hash parameters
to misconfigure, no signature malleability surface, 64-byte signatures, and
verification fast enough to sit in the hot path of every request.

Nothing in this module ever logs key material. The private key is read from the
process environment at call time and is never written to disk or returned in a
loggable form.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)

# Environment-variable NAMES (never values). Composed from a shared prefix so a
# literal credential cannot be introduced here by an edit that mimics the
# surrounding code.
_GATEWAY_ENV_PREFIX = "ADAPTIX_GATEWAY_"

#: JWKS document of PUBLIC verification keys. Every service that verifies a
#: gateway context needs this. Safe to hold — it grants no signing ability.
GATEWAY_PUBLIC_KEYS_ENV = _GATEWAY_ENV_PREFIX + "PUBLIC_KEYS"

#: PKCS#8 PEM of the gateway's Ed25519 PRIVATE key. **Gateway only.** A domain
#: service that is injected this value has recreated the D-053 defect.
GATEWAY_SIGNING_PRIVATE_KEY_ENV = _GATEWAY_ENV_PREFIX + "SIGNING_PRIVATE_KEY"

#: ``kid`` of the key in :data:`GATEWAY_SIGNING_PRIVATE_KEY_ENV`. Stamped into
#: every signed context so verifiers can select the right public key.
GATEWAY_SIGNING_KEY_ID_ENV = _GATEWAY_ENV_PREFIX + "SIGNING_KEY_ID"

#: JOSE algorithm identifier for the only algorithm this trust store accepts.
GATEWAY_SIGNING_ALGORITHM = "EdDSA"

_ED25519_RAW_PUBLIC_KEY_BYTES = 32
_ED25519_SIGNATURE_BYTES = 64


class GatewayKeyError(ValueError):
    """Raised when gateway key material is missing, malformed or unusable.

    Distinct from a signature-verification failure: this names a CONFIGURATION
    fault. Callers surface it as a readiness/503 condition at startup and fail
    closed (never "verify anyway") at request time.
    """


@dataclass(frozen=True)
class GatewayPublicKey:
    """One verification key from the configured JWKS."""

    kid: str
    key: Ed25519PublicKey

    def verify(self, *, signature: bytes, message: bytes) -> bool:
        """Return whether ``signature`` is a valid Ed25519 signature.

        Ed25519 verification is constant-time in the library and has no
        parameters to get wrong, so this reduces to a boolean without leaking
        which stage failed.
        """
        if len(signature) != _ED25519_SIGNATURE_BYTES:
            return False
        try:
            self.key.verify(signature, message)
        except InvalidSignature:
            return False
        return True


def b64url_decode(value: str) -> bytes:
    """Decode unpadded base64url, restoring padding first."""
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def b64url_encode(raw: bytes) -> str:
    """Encode to unpadded base64url."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# Public keyset (verifier side)
# ---------------------------------------------------------------------------

# Parsing the JWKS on every request would put JSON + key construction in the hot
# path. Cache by the RAW env value so a rotated keyset is picked up the moment
# the variable changes (which in ECS means a new task, but tests and any future
# in-process refresh get correct behaviour for free) without ever serving a
# stale key after a change.
_keyset_lock = threading.Lock()
_keyset_cache_source: str | None = None
_keyset_cache: dict[str, GatewayPublicKey] = {}


def _parse_jwks(raw: str) -> dict[str, GatewayPublicKey]:
    """Parse a JWKS document into ``{kid: GatewayPublicKey}``.

    Raises:
        GatewayKeyError: on any malformed document. A partially-parsed keyset is
            never returned — accepting "the keys that happened to parse" is how a
            rotation silently drops the active key and 401s production.
    """
    try:
        doc: Any = json.loads(raw)
    except ValueError as exc:
        raise GatewayKeyError(
            f"{GATEWAY_PUBLIC_KEYS_ENV} is not valid JSON: {exc}"
        ) from exc

    if isinstance(doc, dict) and "keys" in doc:
        entries = doc.get("keys")
    elif isinstance(doc, list):
        entries = doc
    else:
        raise GatewayKeyError(
            f"{GATEWAY_PUBLIC_KEYS_ENV} must be a JWKS object with a 'keys' array"
        )

    if not isinstance(entries, list) or not entries:
        raise GatewayKeyError(f"{GATEWAY_PUBLIC_KEYS_ENV} contains no keys")

    keyset: dict[str, GatewayPublicKey] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise GatewayKeyError(
                f"{GATEWAY_PUBLIC_KEYS_ENV}[{index}] is not an object"
            )

        kid = str(entry.get("kid") or "").strip()
        if not kid:
            raise GatewayKeyError(
                f"{GATEWAY_PUBLIC_KEYS_ENV}[{index}] has no 'kid'; a keyset without "
                "key ids cannot support rotation"
            )
        if kid in keyset:
            raise GatewayKeyError(
                f"{GATEWAY_PUBLIC_KEYS_ENV} declares duplicate kid {kid!r}"
            )

        kty = str(entry.get("kty") or "").strip()
        crv = str(entry.get("crv") or "").strip()
        alg = str(entry.get("alg") or GATEWAY_SIGNING_ALGORITHM).strip()
        if kty != "OKP" or crv != "Ed25519" or alg != GATEWAY_SIGNING_ALGORITHM:
            raise GatewayKeyError(
                f"{GATEWAY_PUBLIC_KEYS_ENV}[{index}] (kid={kid!r}) is "
                f"kty={kty!r} crv={crv!r} alg={alg!r}; only "
                f"OKP/Ed25519/{GATEWAY_SIGNING_ALGORITHM} is accepted"
            )

        x = str(entry.get("x") or "").strip()
        if not x:
            raise GatewayKeyError(
                f"{GATEWAY_PUBLIC_KEYS_ENV}[{index}] (kid={kid!r}) has no 'x'"
            )
        try:
            raw_key = b64url_decode(x)
        except (ValueError, TypeError) as exc:
            raise GatewayKeyError(
                f"{GATEWAY_PUBLIC_KEYS_ENV}[{index}] (kid={kid!r}) 'x' is not base64url"
            ) from exc
        if len(raw_key) != _ED25519_RAW_PUBLIC_KEY_BYTES:
            raise GatewayKeyError(
                f"{GATEWAY_PUBLIC_KEYS_ENV}[{index}] (kid={kid!r}) 'x' decodes to "
                f"{len(raw_key)} bytes, expected {_ED25519_RAW_PUBLIC_KEY_BYTES}"
            )

        keyset[kid] = GatewayPublicKey(
            kid=kid, key=Ed25519PublicKey.from_public_bytes(raw_key)
        )

    return keyset


def _raw_public_keys() -> str:
    return os.environ.get(GATEWAY_PUBLIC_KEYS_ENV, "").strip()


def load_public_keyset() -> dict[str, GatewayPublicKey]:
    """Return the configured verification keyset, parsed and cached.

    Returns:
        ``{kid: GatewayPublicKey}``. Empty dict when the variable is unset —
        "not configured" is a state the caller decides about, not a crash.

    Raises:
        GatewayKeyError: when the variable IS set but malformed. A malformed
            keyset is a deploy fault and must be loud, never silently treated as
            "no keys configured" (which would look identical to a service that
            has not been migrated yet).
    """
    raw = _raw_public_keys()
    if not raw:
        return {}

    global _keyset_cache_source, _keyset_cache
    with _keyset_lock:
        if _keyset_cache_source == raw:
            return _keyset_cache
        parsed = _parse_jwks(raw)
        _keyset_cache_source = raw
        _keyset_cache = parsed
        return parsed


def asymmetric_verification_configured() -> bool:
    """Return whether this process has gateway public keys to verify with."""
    return bool(_raw_public_keys())


def public_key_for_kid(kid: str) -> GatewayPublicKey:
    """Return the verification key named by ``kid``.

    Raises:
        GatewayKeyError: when no keys are configured, or ``kid`` is unknown.
            An unknown ``kid`` is reported with the ids that ARE loaded because
            the overwhelmingly common cause is a rotation where the new public
            key was not distributed before the gateway began signing with it —
            and that is invisible from the message "signature invalid".
    """
    keyset = load_public_keyset()
    if not keyset:
        raise GatewayKeyError(
            f"{GATEWAY_PUBLIC_KEYS_ENV} is not configured; this service cannot "
            "verify gateway-signed contexts"
        )
    key = keyset.get((kid or "").strip())
    if key is None:
        raise GatewayKeyError(
            f"no gateway public key with kid={kid!r} (loaded: "
            f"{sorted(keyset)}); distribute the new public key before the "
            "gateway signs with it"
        )
    return key


def reset_public_keyset_cache() -> None:
    """Drop the parsed-keyset cache. For tests and explicit rotation refresh."""
    global _keyset_cache_source, _keyset_cache
    with _keyset_lock:
        _keyset_cache_source = None
        _keyset_cache = {}


# ---------------------------------------------------------------------------
# Private key (gateway/producer side only)
# ---------------------------------------------------------------------------


def signing_key_id() -> str | None:
    """Return the configured signing ``kid``, or ``None`` when unset."""
    return os.environ.get(GATEWAY_SIGNING_KEY_ID_ENV, "").strip() or None


def asymmetric_signing_configured() -> bool:
    """Return whether this process holds gateway signing material.

    A domain service should ALWAYS see ``False`` here. It returning ``True``
    outside the gateway means the private key was injected somewhere it must not
    be, which is the D-053 defect reintroduced.
    """
    return bool(
        os.environ.get(GATEWAY_SIGNING_PRIVATE_KEY_ENV, "").strip() and signing_key_id()
    )


def load_signing_key() -> tuple[str, Ed25519PrivateKey]:
    """Return ``(kid, private_key)`` for signing gateway contexts.

    Raises:
        GatewayKeyError: when the private key or its ``kid`` is missing or the
            PEM is not an Ed25519 PKCS#8 private key.
    """
    pem = os.environ.get(GATEWAY_SIGNING_PRIVATE_KEY_ENV, "").strip()
    if not pem:
        raise GatewayKeyError(
            f"{GATEWAY_SIGNING_PRIVATE_KEY_ENV} is not configured; only the "
            "gateway may hold gateway signing material"
        )
    kid = signing_key_id()
    if not kid:
        raise GatewayKeyError(
            f"{GATEWAY_SIGNING_KEY_ID_ENV} is not configured; a signed context "
            "without a key id cannot be verified after rotation"
        )

    try:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception as exc:
        raise GatewayKeyError(
            f"{GATEWAY_SIGNING_PRIVATE_KEY_ENV} is not a readable PEM private key"
        ) from exc

    if not isinstance(key, Ed25519PrivateKey):
        raise GatewayKeyError(
            f"{GATEWAY_SIGNING_PRIVATE_KEY_ENV} is not an Ed25519 key; only "
            f"{GATEWAY_SIGNING_ALGORITHM} signing is accepted"
        )
    return kid, key


# ---------------------------------------------------------------------------
# Provisioning helpers (ops / tests — never used on the request path)
# ---------------------------------------------------------------------------


def generate_signing_keypair(kid: str) -> tuple[str, dict[str, str]]:
    """Generate a fresh Ed25519 keypair for provisioning or tests.

    Args:
        kid: Key id to stamp into the JWKS entry. Use a rotation-legible value
            such as ``gw-2026-08``.

    Returns:
        ``(private_key_pem, jwks_entry)``. The PEM goes into Secrets Manager and
        is injected ONLY into the gateway task definition; the JWKS entry is
        published to every verifying service.
    """
    if not (kid or "").strip():
        raise GatewayKeyError("kid is required to generate a signing keypair")

    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    return pem, public_jwks_entry(kid=kid.strip(), public_key=private.public_key())


def public_jwks_entry(*, kid: str, public_key: Ed25519PublicKey) -> dict[str, str]:
    """Return the JWKS entry publishing ``public_key`` under ``kid``."""
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "alg": GATEWAY_SIGNING_ALGORITHM,
        "use": "sig",
        "kid": kid,
        "x": b64url_encode(raw),
    }


def build_jwks(entries: list[dict[str, str]]) -> str:
    """Serialize JWKS ``entries`` into the value of the public-keys variable."""
    return json.dumps({"keys": list(entries)}, separators=(",", ":"), sort_keys=True)


__all__ = [
    "GATEWAY_PUBLIC_KEYS_ENV",
    "GATEWAY_SIGNING_ALGORITHM",
    "GATEWAY_SIGNING_KEY_ID_ENV",
    "GATEWAY_SIGNING_PRIVATE_KEY_ENV",
    "GatewayKeyError",
    "GatewayPublicKey",
    "asymmetric_signing_configured",
    "asymmetric_verification_configured",
    "b64url_decode",
    "b64url_encode",
    "build_jwks",
    "generate_signing_keypair",
    "load_public_keyset",
    "load_signing_key",
    "public_jwks_entry",
    "public_key_for_kid",
    "reset_public_keyset_cache",
    "signing_key_id",
]
