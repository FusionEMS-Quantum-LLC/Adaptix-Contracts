"""Shared encrypting Temporal ``PayloadCodec`` for the Adaptix platform.

Every value a workflow accepts, returns, signals, queries, or passes to an
activity is serialised into a Temporal ``Payload`` and written into workflow
history on the Temporal server's Postgres database. This codec makes "no
plaintext PII in workflow history" a real, enforced boundary instead of a
docstring convention: payload bytes are encrypted with AES-256-GCM before
they leave the process that holds the key, and decrypted only inside a
process that also holds it. The Temporal server, its RDS instance, its
backups, and anyone reading history through the Temporal UI or ``tctl`` see
ciphertext only.

Why this lives in ``adaptix-contracts``
----------------------------------------
Temporal requires the SAME ``PayloadCodec`` on every side of a workflow: the
worker that executes it AND every client that starts it, signals it, queries
it, or reads its result. A codec wired into only one side does not protect
that side's traffic — the Temporal SDK converts values to ``Payload`` bytes
at the call site, so an unwired client writes plaintext to history no matter
how well the worker encrypts. ``adaptix-contracts`` is the one place both a
Temporal worker fleet (``Adaptix-Temporal-Service``) and every Temporal
CLIENT (``Adaptix-Billing-Service`` and any future workflow-starting service)
can share one implementation instead of maintaining parallel copies that are
free to drift apart on wire format, key handling, or fail-closed behaviour.

This module is additive and optional: it is not imported by
``adaptix_contracts/__init__.py`` or re-exported through
``adaptix_contracts.schemas``, and importing it requires the ``temporal``
extra (``pip install adaptix-contracts[temporal]``) because it depends on
``temporalio``, which most Contracts consumers never touch. A consumer that
does not import this module pays nothing for its existence.

Wire format — byte-for-byte compatible with the AES-256-GCM codec
``Adaptix-Temporal-Service`` has run in production since 2026-08-16
(``backend/temporal_app/codec.py``, introduced in that repo's PR #51)
------------------------------------------------------------------------
``encode()`` replaces each inbound ``Payload`` with a NEW ``Payload``:

    metadata:
        encoding             = b"binary/encrypted"
        encryption-key-id    = <key id that encrypted this payload>
        encryption-algorithm = b"AES-256-GCM"
    data:
        <12-byte nonce> || <AES-GCM ciphertext of the original serialised Payload>

The ORIGINAL payload (its own metadata AND data) is serialised with
``Payload.SerializeToString()`` and encrypted whole, so the original encoding
metadata (``json/plain``, ``binary/null``, …) is itself hidden and restored
exactly on decode.

``tests/test_temporal_payload_codec.py`` in this repository pins golden
ciphertext vectors produced by ``Adaptix-Temporal-Service``'s own codec (both
the keyring-JSON key shape and the bare-base64 key shape) and asserts this
module decodes them correctly, and separately asserts this module's own
``encode()`` output is byte-identical to that codec's output for the same
key, nonce, and plaintext. Any accidental drift in metadata keys, nonce
placement, key derivation, or the encrypted-plaintext framing fails that
suite, not just a production replay.

Fail-closed rules — read before changing anything here
--------------------------------------------------------
1. ``encode()`` NEVER emits plaintext when a key is expected. With no usable
   key it raises :class:`PayloadCodecError`. A caller that cannot encrypt
   does not get to write to history "just this once" — this applies equally
   to a worker executing a workflow and a client starting one.
2. ``decode()`` raises on any payload MARKED ``binary/encrypted`` that it
   cannot decrypt — unknown key id, missing key, or a failed GCM
   authentication tag (which means tampering or corruption).
3. ``decode()`` PASSES THROUGH payloads that carry no encrypted marker. That
   is not fail-open. Adaptix already has completed and in-flight workflow
   histories written before a given call site adopted this codec; those
   payloads are plaintext and must stay readable or every one of them breaks
   on replay. Only decode is permissive, and only for payloads that were
   never encrypted in the first place.
4. Plaintext passthrough on ENCODE exists solely for local development and
   test suites. It requires the explicit
   ``TEMPORAL_PAYLOAD_CODEC_PLAINTEXT_LOCAL`` flag, that flag defaults OFF,
   and it is REFUSED outright when ``ENVIRONMENT`` names a production
   environment.

Key material
------------
The key arrives the same way every other Adaptix worker/service secret
arrives: AWS Secrets Manager -> ECS task definition ``secrets`` block ->
environment variable. A process reads ``TEMPORAL_PAYLOAD_CODEC_KEY`` and
never calls Secrets Manager itself.

Two secret shapes are accepted:

* A keyring JSON object — the production shape, because it supports rotation::

      {"primary_key_id": "2026-08", "keys": {"2026-08": "<base64 32 bytes>"}}

  ``primary_key_id`` names the key used to ENCRYPT. Every entry in ``keys``
  can DECRYPT. Rotating means adding a new entry and repointing
  ``primary_key_id`` — the retired key stays in ``keys`` so open workflows
  and historical runs encrypted under it remain readable. Removing a key
  that any live history still uses is what breaks replay, so retire keys
  only after the runs that used them have closed.

* A bare base64-encoded 32-byte key — convenience for local development. Its
  key id is derived as a SHA-256 fingerprint of the key bytes
  (``sha256(raw).hexdigest()[:16]``), so it is stable but carries no
  rotation story. This derivation MUST stay byte-identical across every
  consumer of this module — a client and a worker that derive different key
  ids for the same bare key would each tag their own payloads with an id the
  other cannot look up in its own keyring.

Security
--------
* Key material is never logged, never returned, and never placed in an
  exception message. Errors name the key ID (an opaque label) and the
  failure mode only.
* Plaintext payload bytes are never logged. Payload contents may carry PII —
  ``adaptix-contracts`` is a PUBLIC repository, so this module and its tests
  use only synthetic keys and synthetic payloads, never a real deployed key
  or real customer data.
* A fresh 12-byte nonce is generated per payload from ``os.urandom``. This
  codec belongs on the IO path only — never inside a Temporal workflow
  sandbox, where non-deterministic randomness would break replay
  determinism.
"""

from __future__ import annotations

import base64
import binascii
import dataclasses
import hashlib
import json
import logging
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from temporalio.api.common.v1 import Payload
from temporalio.converter import DataConverter, PayloadCodec

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Environment variable names — identical across every consumer of this
# module. Keeping them here (instead of letting each consumer define its own
# string literal) is what makes "same TEMPORAL_PAYLOAD_CODEC_KEY env var
# everywhere" an enforced fact instead of a convention two repos could drift
# apart on.
# --------------------------------------------------------------------------

#: The payload encryption keyring. Required in every environment that does
#: not set the local plaintext flag.
PAYLOAD_CODEC_KEY_ENV: str = "TEMPORAL_PAYLOAD_CODEC_KEY"

#: Explicit local/test escape hatch that disables payload encryption on
#: ENCODE. Defaults OFF and is refused when ``ENVIRONMENT`` names a
#: production environment.
PAYLOAD_CODEC_PLAINTEXT_ENV: str = "TEMPORAL_PAYLOAD_CODEC_PLAINTEXT_LOCAL"

#: Deployment environment name (e.g. ``"production"`` in AWS ECS task
#: definitions).
ENVIRONMENT_ENV: str = "ENVIRONMENT"

#: Values of ``ENVIRONMENT`` that mean "real customer data lives here".
#: Matched case-insensitively. Anything in this set forbids unencrypted
#: payloads on encode.
PRODUCTION_ENVIRONMENTS: frozenset[str] = frozenset({"production", "prod"})


def is_production_environment(value: str | None) -> bool:
    """Return True when ``value`` names a production environment.

    Pure and case/whitespace tolerant so the same rule applies everywhere
    this module is used: the module constant, a value read live from the
    process environment, and tests.
    """
    return (value or "").strip().lower() in PRODUCTION_ENVIRONMENTS


def env_flag_is_true(value: str | None) -> bool:
    """Interpret an environment variable as a boolean flag, defaulting False.

    Only an explicit affirmative enables a flag. Anything else — unset,
    empty, "0", "false", "off", or a typo — is False, so a safety flag can
    never be switched on by accident.
    """
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------
# Wire-format constants
# --------------------------------------------------------------------------

#: ``encoding`` metadata value that marks a payload as produced by this codec.
ENCRYPTED_ENCODING: bytes = b"binary/encrypted"

#: Metadata key carrying the id of the key that encrypted the payload. Read on
#: decode to select the right key from the keyring during a rotation window.
METADATA_KEY_ID: str = "encryption-key-id"

#: Metadata key carrying the algorithm name, so a future algorithm change can
#: be detected rather than silently mis-decrypted.
METADATA_ALGORITHM: str = "encryption-algorithm"

#: The only algorithm this codec writes. AES-256-GCM is authenticated
#: encryption: a modified ciphertext fails the tag check instead of decrypting
#: to garbage.
ALGORITHM: bytes = b"AES-256-GCM"

#: AES-GCM key length in bytes (256-bit).
KEY_LENGTH_BYTES: int = 32

#: AES-GCM nonce length in bytes. 96-bit is the NIST-recommended GCM nonce size
#: and what ``AESGCM`` is optimised for.
NONCE_LENGTH_BYTES: int = 12


class PayloadCodecError(RuntimeError):
    """Raised when a payload cannot be encrypted or decrypted.

    Treated as fatal, not transient. Every cause — no key configured, an
    unknown key id, a failed authentication tag — is a deployment or
    integrity problem that retrying the same call cannot resolve.
    """


# --------------------------------------------------------------------------
# Keyring
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Keyring:
    """The set of AES-256 keys a process can use, plus which one encrypts.

    ``keys`` maps key id -> 32 raw key bytes. ``primary_key_id`` must be a key
    in that mapping and is the one ``encode()`` uses. Every key in the mapping
    can decrypt, which is what makes rotation possible without breaking the
    histories written under a retired key.
    """

    primary_key_id: str
    keys: dict[str, bytes]

    def __post_init__(self) -> None:
        if not self.keys:
            raise PayloadCodecError("payload codec keyring contains no keys")
        if self.primary_key_id not in self.keys:
            raise PayloadCodecError(
                f"payload codec keyring primary_key_id '{self.primary_key_id}' "
                "is not present in its own key set"
            )

    @property
    def primary_key(self) -> bytes:
        return self.keys[self.primary_key_id]

    def key_for(self, key_id: str) -> bytes:
        """Return the key for ``key_id`` or raise if it is not held."""
        key = self.keys.get(key_id)
        if key is None:
            raise PayloadCodecError(
                f"payload was encrypted with key id '{key_id}', which this "
                "process does not hold. Add that key to the payload codec "
                "secret (retired keys must stay in the keyring while any "
                "history that used them is still readable)."
            )
        return key

    @staticmethod
    def _decode_key(key_id: str, encoded: object) -> bytes:
        """Base64-decode one key and enforce the AES-256 length.

        The key VALUE never appears in an error message — only its id.
        """
        if not isinstance(encoded, str) or not encoded.strip():
            raise PayloadCodecError(
                f"payload codec key '{key_id}' is not a base64 string"
            )
        try:
            raw = base64.b64decode(encoded.strip(), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise PayloadCodecError(
                f"payload codec key '{key_id}' is not valid base64"
            ) from exc
        if len(raw) != KEY_LENGTH_BYTES:
            raise PayloadCodecError(
                f"payload codec key '{key_id}' must decode to "
                f"{KEY_LENGTH_BYTES} bytes (AES-256); got {len(raw)}"
            )
        return raw

    @classmethod
    def from_secret_value(cls, secret_value: str) -> Keyring:
        """Build a keyring from the raw ``TEMPORAL_PAYLOAD_CODEC_KEY`` value.

        Accepts the production keyring JSON object or a bare base64 key
        (local development). Raises :class:`PayloadCodecError` on anything
        else — a malformed secret must stop the process, not silently
        degrade it.
        """
        value = (secret_value or "").strip()
        if not value:
            raise PayloadCodecError(
                f"{PAYLOAD_CODEC_KEY_ENV} is empty — no payload encryption "
                "key is configured."
            )

        if value.startswith("{"):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise PayloadCodecError(
                    f"{PAYLOAD_CODEC_KEY_ENV} starts with '{{' but is not "
                    "valid JSON. Expected "
                    '{"primary_key_id": "...", "keys": {"...": "<base64>"}}.'
                ) from exc
            if not isinstance(parsed, dict):
                raise PayloadCodecError(
                    f"{PAYLOAD_CODEC_KEY_ENV} JSON must be an object"
                )

            raw_keys = parsed.get("keys")
            if not isinstance(raw_keys, dict) or not raw_keys:
                raise PayloadCodecError(
                    f"{PAYLOAD_CODEC_KEY_ENV} JSON must carry a non-empty "
                    "'keys' object mapping key id -> base64 key"
                )
            primary = parsed.get("primary_key_id")
            if not isinstance(primary, str) or not primary.strip():
                raise PayloadCodecError(
                    f"{PAYLOAD_CODEC_KEY_ENV} JSON must carry a "
                    "'primary_key_id' string"
                )

            keys = {
                str(key_id): cls._decode_key(str(key_id), encoded)
                for key_id, encoded in raw_keys.items()
            }
            return cls(primary_key_id=primary.strip(), keys=keys)

        # Bare base64 key. Derive a stable, non-secret id from the key bytes
        # so payload metadata still names the key that encrypted it. This
        # derivation is part of the wire contract: every consumer of this
        # module must compute the same id for the same bare key, or a client
        # and a worker sharing one bare key would tag payloads with ids the
        # other side cannot resolve.
        raw = cls._decode_key("derived", value)
        key_id = hashlib.sha256(raw).hexdigest()[:16]
        return cls(primary_key_id=key_id, keys={key_id: raw})


# --------------------------------------------------------------------------
# Codec
# --------------------------------------------------------------------------


class EncryptionPayloadCodec(PayloadCodec):
    """AES-256-GCM ``PayloadCodec`` for Adaptix Temporal payloads.

    Construct with :meth:`from_environment` in process-startup paths (a
    worker's ``main()`` or a client's connection helper). The explicit
    constructor exists for tests, which need to build a codec with a known
    keyring without touching process environment.
    """

    def __init__(
        self,
        keyring: Keyring | None,
        *,
        plaintext_passthrough: bool = False,
    ) -> None:
        if keyring is None and not plaintext_passthrough:
            raise PayloadCodecError(
                "EncryptionPayloadCodec requires a keyring unless plaintext "
                "passthrough is explicitly enabled for local development."
            )
        self._keyring = keyring
        self._plaintext_passthrough = plaintext_passthrough

    # -- construction ------------------------------------------------------ #
    @classmethod
    def from_environment(cls) -> EncryptionPayloadCodec:
        """Build the codec from process environment, failing closed.

        Reads the environment live (rather than import-time constants) so a
        process started after its ECS secret injection, and a test using
        ``monkeypatch.setenv``, both observe the same values.

        Raises :class:`PayloadCodecError` when:
          * the plaintext flag is set in a production environment, or
          * no key is configured and the plaintext flag is not set, or
          * the configured secret is malformed.
        """
        environment = os.environ.get(ENVIRONMENT_ENV, "").strip()
        plaintext_requested = env_flag_is_true(
            os.environ.get(PAYLOAD_CODEC_PLAINTEXT_ENV)
        )
        secret_value = os.environ.get(PAYLOAD_CODEC_KEY_ENV, "")

        if plaintext_requested and is_production_environment(environment):
            raise PayloadCodecError(
                f"{PAYLOAD_CODEC_PLAINTEXT_ENV} is set but "
                f"{ENVIRONMENT_ENV}='{environment}' is a production "
                "environment. Unencrypted Temporal payloads are never "
                f"permitted in production. Remove the flag and provision "
                f"{PAYLOAD_CODEC_KEY_ENV}."
            )

        if secret_value.strip():
            keyring = Keyring.from_secret_value(secret_value)
            logger.info(
                "payload_codec.enabled algorithm=%s primary_key_id=%s "
                "decrypt_key_count=%d; key material not logged",
                ALGORITHM.decode(),
                keyring.primary_key_id,
                len(keyring.keys),
            )
            return cls(keyring)

        if plaintext_requested:
            logger.warning(
                "payload_codec.plaintext_passthrough_enabled environment=%s "
                "— Temporal payloads are NOT encrypted. This is permitted "
                "only for local development and tests; PII must never be "
                "sent through this process in this mode.",
                environment or "unset",
            )
            return cls(None, plaintext_passthrough=True)

        raise PayloadCodecError(
            f"{PAYLOAD_CODEC_KEY_ENV} is not configured, so Temporal "
            "payloads cannot be encrypted. Provision the payload codec key "
            "via AWS Secrets Manager and inject it in the ECS task "
            f"definition. For local development only, set "
            f"{PAYLOAD_CODEC_PLAINTEXT_ENV}=true."
        )

    # -- introspection ----------------------------------------------------- #
    @property
    def is_encrypting(self) -> bool:
        """True when this codec encrypts on encode (i.e. not in passthrough)."""
        return self._keyring is not None

    @property
    def primary_key_id(self) -> str | None:
        """The key id used to encrypt, or ``None`` in passthrough mode."""
        return self._keyring.primary_key_id if self._keyring else None

    # -- PayloadCodec ------------------------------------------------------ #
    async def encode(self, payloads):  # type: ignore[no-untyped-def]
        """Encrypt each payload, or pass through in explicit local mode.

        Never emits plaintext when a keyring is present, and never falls back
        to plaintext when encryption fails.
        """
        if self._keyring is None:
            # Reachable only via the explicit local-development flag; the
            # constructor refuses a keyless codec otherwise.
            return list(payloads)

        keyring = self._keyring
        key = keyring.primary_key
        key_id = keyring.primary_key_id
        aesgcm = AESGCM(key)

        encoded: list[Payload] = []
        for payload in payloads:
            nonce = os.urandom(NONCE_LENGTH_BYTES)
            ciphertext = aesgcm.encrypt(nonce, payload.SerializeToString(), None)
            encoded.append(
                Payload(
                    metadata={
                        "encoding": ENCRYPTED_ENCODING,
                        METADATA_KEY_ID: key_id.encode("utf-8"),
                        METADATA_ALGORITHM: ALGORITHM,
                    },
                    data=nonce + ciphertext,
                )
            )
        return encoded

    async def decode(self, payloads):  # type: ignore[no-untyped-def]
        """Decrypt payloads this codec produced; pass through everything else.

        A payload marked ``binary/encrypted`` that cannot be decrypted
        raises. A payload with no encrypted marker is returned untouched —
        it predates this codec's adoption on this call site and was never
        encrypted (see the module docstring).
        """
        decoded: list[Payload] = []
        for payload in payloads:
            if payload.metadata.get("encoding") != ENCRYPTED_ENCODING:
                decoded.append(payload)
                continue

            algorithm = payload.metadata.get(METADATA_ALGORITHM, b"")
            if algorithm != ALGORITHM:
                raise PayloadCodecError(
                    "encrypted payload declares unsupported algorithm "
                    f"'{algorithm.decode('utf-8', 'replace')}'; this codec "
                    f"implements {ALGORITHM.decode()} only."
                )

            if self._keyring is None:
                raise PayloadCodecError(
                    "received an encrypted Temporal payload but this "
                    "process has no payload codec key. Provision "
                    f"{PAYLOAD_CODEC_KEY_ENV} — plaintext passthrough "
                    "cannot read encrypted history."
                )

            key_id = payload.metadata.get(METADATA_KEY_ID, b"").decode(
                "utf-8", "replace"
            )
            key = self._keyring.key_for(key_id)

            raw = payload.data
            if len(raw) <= NONCE_LENGTH_BYTES:
                raise PayloadCodecError(
                    f"encrypted payload (key id '{key_id}') is truncated: "
                    f"{len(raw)} bytes cannot hold a nonce plus ciphertext."
                )

            nonce, ciphertext = raw[:NONCE_LENGTH_BYTES], raw[NONCE_LENGTH_BYTES:]
            try:
                plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
            except InvalidTag as exc:
                raise PayloadCodecError(
                    f"encrypted payload (key id '{key_id}') failed its "
                    "authentication tag. The ciphertext was modified or the "
                    "key under that id is not the key that encrypted it."
                ) from exc

            restored = Payload()
            restored.ParseFromString(plaintext)
            decoded.append(restored)
        return decoded


# --------------------------------------------------------------------------
# Data converter wiring
# --------------------------------------------------------------------------


def build_data_converter(
    codec: PayloadCodec | None = None,
) -> DataConverter:
    """Return the Adaptix ``DataConverter``: SDK defaults plus this codec.

    Only the codec slot is replaced. The default payload converter and
    failure converter are kept so JSON/proto/binary values, and Temporal's
    own failure shapes, continue to serialise exactly as they always have —
    the bytes are simply encrypted afterwards.

    Passing ``codec`` explicitly is for tests; production callers omit it
    and get :meth:`EncryptionPayloadCodec.from_environment`, which fails
    closed.
    """
    return dataclasses.replace(
        DataConverter.default,
        payload_codec=codec
        if codec is not None
        else EncryptionPayloadCodec.from_environment(),
    )
