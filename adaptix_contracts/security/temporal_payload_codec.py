"""Encrypting Temporal ``PayloadCodec`` — the CANONICAL Adaptix implementation.

This is the ONE definition of the Adaptix Temporal payload wire format. It
lives in Contracts, not in a service, because more than one service must
produce and consume it: a Temporal worker decodes history, and any service
that STARTS a workflow encodes the initial payload with its OWN client's
converter. Two copies of a cryptographic wire format that drift apart mean
history written by one side stops decoding on the other, so there is exactly
one copy and both sides import it.

Every value a workflow accepts, returns, signals, queries, or passes to an
activity is serialised into a Temporal ``Payload`` and written into workflow
history on the Temporal server's Postgres database. Before this module existed,
those bytes were stored as plaintext JSON and "no PHI in workflow history" was a
docstring convention with nothing enforcing it.

This codec makes the boundary real: payload bytes are encrypted with
AES-256-GCM before they leave the encoding process and decrypted only inside a
process that holds the key. The Temporal server, its RDS instance, its backups,
and anyone reading history through the Temporal UI or ``tctl`` see ciphertext.

Wire format
-----------
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

Fail-closed rules — read before changing anything here
------------------------------------------------------
1. ``encode()`` NEVER emits plaintext when a key is expected. With no usable
   key it raises :class:`PayloadCodecError`. A process that cannot encrypt does
   not get to write to history "just this once".
2. ``decode()`` raises on any payload MARKED ``binary/encrypted`` that it
   cannot decrypt — unknown key id, missing key, or a failed GCM
   authentication tag (which means tampering or corruption).
3. ``decode()`` PASSES THROUGH payloads that carry no encrypted marker. That is
   not fail-open. Adaptix already has completed and in-flight workflow
   histories (claim submission, ERA posting, agency onboarding) written before
   this codec shipped; those payloads are plaintext and must stay readable or
   every one of them breaks on replay. Only decode is permissive, and only for
   payloads that were never encrypted in the first place.
4. Plaintext passthrough on ENCODE exists solely for local development and the
   test suite. It requires the explicit ``TEMPORAL_PAYLOAD_CODEC_PLAINTEXT_LOCAL``
   flag, that flag defaults OFF, and it is REFUSED outright when ``ENVIRONMENT``
   names a production environment.

Key material
------------
The key arrives the same way every other Adaptix service secret arrives: AWS
Secrets Manager -> ECS task definition ``secrets`` block -> environment
variable. The process reads ``TEMPORAL_PAYLOAD_CODEC_KEY`` and never calls
Secrets Manager itself, exactly as ``system_token_client`` reads
``CORE_PROVISIONING_TOKEN``.

Two secret shapes are accepted:

* A keyring JSON object — the production shape, because it supports rotation::

      {"primary_key_id": "2026-08", "keys": {"2026-08": "<base64 32 bytes>"}}

  ``primary_key_id`` names the key used to ENCRYPT. Every entry in ``keys`` can
  DECRYPT. Rotating means adding a new entry and repointing
  ``primary_key_id`` — the retired key stays in ``keys`` so open workflows and
  historical runs encrypted under it remain readable. Removing a key that any
  live history still uses is what breaks replay, so retire keys only after the
  runs that used them have closed.

* A bare base64-encoded 32-byte key — convenience for local development. Its
  key id is derived as a SHA-256 fingerprint of the key bytes, so it is stable
  but carries no rotation story.

Security
--------
* Key material is never logged, never returned, and never placed in an
  exception message. Errors name the key ID (an opaque label) and the failure
  mode only.
* Plaintext payload bytes are never logged. Payload contents may carry PHI;
  that is the entire reason this module exists.
* A fresh 12-byte nonce is generated per payload from ``os.urandom``. The codec
  runs on the worker's IO path, never inside the workflow sandbox, so
  non-deterministic randomness here is correct and does not affect replay.
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

from adaptix_contracts.environment import (
    ENVIRONMENT_ENV,
    PRODUCTION_ENVIRONMENTS as PRODUCTION_ENVIRONMENTS,
    is_production_environment,
)

# temporalio (and the protobuf runtime it pulls in) is an EXTRA, not a base
# dependency of adaptix-contracts - see the `[project.optional-dependencies]`
# `temporal` table in pyproject.toml. Importing this module without that extra
# installed otherwise fails with a bare "No module named 'google'", which names
# protobuf's namespace package and gives the caller nothing to act on. Re-raise
# with the actual remedy, preserving the original exception type and cause so
# `except ModuleNotFoundError` and `except ImportError` both still behave as
# before for callers that already handle a missing optional dependency.
try:
    from google.protobuf.message import DecodeError
    from temporalio.api.common.v1 import Payload
    from temporalio.converter import DataConverter, PayloadCodec
except ModuleNotFoundError as exc:  # pragma: no cover - import-time guard
    raise ModuleNotFoundError(
        f"{exc.msg}. adaptix_contracts.security.temporal_payload_codec requires "
        "the Temporal SDK, which adaptix-contracts declares as an optional "
        "extra. Install it with: pip install 'adaptix-contracts[temporal]'",
        name=exc.name,
        path=exc.path,
    ) from exc

#: Environment variable names this codec reads. PAYLOAD_CODEC_KEY_ENV and
#: PAYLOAD_CODEC_PLAINTEXT_ENV are declared here (rather than imported from
#: any one service) because the codec is now shared: the variable NAMES are
#: part of the contract, exactly like the wire format below.
#:
#: ENVIRONMENT_ENV and is_production_environment (used just below) are
#: imported unchanged from adaptix_contracts.environment, the canonical,
#: single-source definition -- this module used to carry its own independent
#: copy of both, plus its own PRODUCTION_ENVIRONMENTS set, which is exactly
#: the drift that module now closes. PRODUCTION_ENVIRONMENTS is re-exported
#: here (the explicit `as PRODUCTION_ENVIRONMENTS` self-alias is the PEP 484
#: re-export idiom -- it tells ruff/mypy this import is intentionally public,
#: not dead) purely for import-path compatibility: this module used to define
#: it directly, so `from adaptix_contracts.security.temporal_payload_codec
#: import PRODUCTION_ENVIRONMENTS` must keep resolving even though nothing in
#: this file uses the name directly any more.
PAYLOAD_CODEC_KEY_ENV: str = "TEMPORAL_PAYLOAD_CODEC_KEY"
PAYLOAD_CODEC_PLAINTEXT_ENV: str = "TEMPORAL_PAYLOAD_CODEC_PLAINTEXT_LOCAL"


def env_flag_is_true(value: str | None) -> bool:
    """Interpret an environment variable as a boolean flag, defaulting to False.

    Only an explicit affirmative enables a flag. Anything else — unset, empty,
    "0", "false", "off", or a typo — is False, so a safety flag can never be
    switched on by accident.
    """
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


logger = logging.getLogger(__name__)

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
    unknown key id, a failed authentication tag — is a deployment or integrity
    problem that retrying the same call cannot resolve.
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
        """The key bytes for :attr:`primary_key_id` — the key ``encode()`` uses."""
        return self.keys[self.primary_key_id]

    def key_for(self, key_id: str) -> bytes:
        """Return the key for ``key_id`` or raise if it is not held."""
        key = self.keys.get(key_id)
        if key is None:
            raise PayloadCodecError(
                f"payload was encrypted with key id '{key_id}', which this process "
                "does not hold. Add that key to the payload codec secret "
                "(retired keys must stay in the keyring while any history that "
                "used them is still readable)."
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

        Accepts the production keyring JSON object or a bare base64 key (local
        development). Raises :class:`PayloadCodecError` on anything else — a
        malformed secret must stop the process, not silently degrade it.
        """
        value = (secret_value or "").strip()
        if not value:
            raise PayloadCodecError(
                f"{PAYLOAD_CODEC_KEY_ENV} is empty — no payload encryption "
                "key is configured."
            )

        if value.startswith("{"):
            return cls._parse_json_keyring(value)

        return cls._parse_bare_key(value)

    @classmethod
    def _parse_json_keyring(cls, value: str) -> Keyring:
        """Parse and validate the JSON keyring shape of the codec secret.

        Extracted from :meth:`from_secret_value` to keep that fail-closed
        entry point short and auditable, per the Codacy review of this
        module. Behavior is unchanged: same JSON shape, same validation,
        same errors.
        """
        parsed = cls._load_keyring_json(value)
        raw_keys, primary = cls._require_keyring_fields(parsed)
        keys = {
            str(key_id): cls._decode_key(str(key_id), encoded)
            for key_id, encoded in raw_keys.items()
        }
        return cls(primary_key_id=primary.strip(), keys=keys)

    @staticmethod
    def _load_keyring_json(value: str) -> dict:
        """Parse the keyring secret as a JSON object, or raise.

        Extracted from :meth:`from_secret_value`; behavior unchanged.
        """
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PayloadCodecError(
                f"{PAYLOAD_CODEC_KEY_ENV} starts with '{{' but is not "
                "valid JSON. Expected "
                '{"primary_key_id": "...", "keys": {"...": "<base64>"}}.'
            ) from exc
        if not isinstance(parsed, dict):
            raise PayloadCodecError(f"{PAYLOAD_CODEC_KEY_ENV} JSON must be an object")
        return parsed

    @staticmethod
    def _require_keyring_fields(parsed: dict) -> tuple[dict, str]:
        """Validate and return the ``keys`` and ``primary_key_id`` JSON fields.

        Extracted from :meth:`from_secret_value`; behavior unchanged.
        """
        raw_keys = parsed.get("keys")
        if not isinstance(raw_keys, dict) or not raw_keys:
            raise PayloadCodecError(
                f"{PAYLOAD_CODEC_KEY_ENV} JSON must carry a non-empty "
                "'keys' object mapping key id -> base64 key"
            )
        primary = parsed.get("primary_key_id")
        if not isinstance(primary, str) or not primary.strip():
            raise PayloadCodecError(
                f"{PAYLOAD_CODEC_KEY_ENV} JSON must carry a 'primary_key_id' string"
            )
        return raw_keys, primary

    @classmethod
    def _parse_bare_key(cls, value: str) -> Keyring:
        """Build a single-key keyring from a bare base64 key (local development).

        Extracted from :meth:`from_secret_value`; behavior unchanged. Derives a
        stable, non-secret id from the key bytes so payload metadata still
        names the key that encrypted it.
        """
        raw = cls._decode_key("derived", value)
        key_id = hashlib.sha256(raw).hexdigest()[:16]
        return cls(primary_key_id=key_id, keys={key_id: raw})


# --------------------------------------------------------------------------
# Codec
# --------------------------------------------------------------------------


class EncryptionPayloadCodec(PayloadCodec):
    """AES-256-GCM ``PayloadCodec`` for Adaptix Temporal payloads.

    Construct with :meth:`from_environment` in worker and client startup paths. The
    explicit constructor exists for tests, which need to build a codec with a
    known keyring without touching process environment.
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
                "environment. Unencrypted Temporal payloads are never permitted "
                "in production. Remove the flag and provision "
                f"{PAYLOAD_CODEC_KEY_ENV}."
            )

        if secret_value.strip():
            return cls._from_configured_secret(secret_value)

        return cls._from_unconfigured_secret(plaintext_requested, environment)

    @classmethod
    def _from_configured_secret(cls, secret_value: str) -> EncryptionPayloadCodec:
        """Build an encrypting codec once a payload codec secret is present.

        Extracted from :meth:`from_environment`, per the Codacy review of this
        module; behavior unchanged.
        """
        keyring = Keyring.from_secret_value(secret_value)
        logger.info(
            "payload_codec.enabled algorithm=%s primary_key_id=%s "
            "decrypt_key_count=%d; key material not logged",
            ALGORITHM.decode(),
            keyring.primary_key_id,
            len(keyring.keys),
        )
        return cls(keyring)

    @classmethod
    def _from_unconfigured_secret(
        cls, plaintext_requested: bool, environment: str
    ) -> EncryptionPayloadCodec:
        """Build a passthrough codec, or fail closed, with no secret configured.

        Extracted from :meth:`from_environment`; behavior unchanged.
        """
        if plaintext_requested:
            logger.warning(
                "payload_codec.plaintext_passthrough_enabled environment=%s — "
                "Temporal payloads are NOT encrypted. This is permitted only for "
                "local development and tests; PHI must never be sent through a "
                "process in this mode.",
                environment or "unset",
            )
            return cls(None, plaintext_passthrough=True)

        raise PayloadCodecError(
            f"{PAYLOAD_CODEC_KEY_ENV} is not configured, so Temporal "
            "payloads cannot be encrypted. Provision the payload codec key via "
            "AWS Secrets Manager and inject it in the ECS task definition. For "
            f"local development only, set {PAYLOAD_CODEC_PLAINTEXT_ENV}=true."
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

        Never emits plaintext when a keyring is present, and never falls back to
        plaintext when encryption fails.
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
            encoded.append(self._encrypt_payload(payload, aesgcm, key_id))
        return encoded

    @staticmethod
    def _encrypt_payload(payload: Payload, aesgcm: AESGCM, key_id: str) -> Payload:
        """Encrypt one payload under ``aesgcm`` with a fresh nonce.

        Extracted from :meth:`encode` to bring it under the method-length
        limit, per the Codacy review of this module; behavior unchanged.
        """
        nonce = os.urandom(NONCE_LENGTH_BYTES)
        ciphertext = aesgcm.encrypt(nonce, payload.SerializeToString(), None)
        return Payload(
            metadata={
                "encoding": ENCRYPTED_ENCODING,
                METADATA_KEY_ID: key_id.encode("utf-8"),
                METADATA_ALGORITHM: ALGORITHM,
            },
            data=nonce + ciphertext,
        )

    async def decode(self, payloads):  # type: ignore[no-untyped-def]
        """Decrypt payloads this codec produced; pass through everything else.

        A payload marked ``binary/encrypted`` that cannot be decrypted raises.
        A payload with no encrypted marker is returned untouched — it predates
        this codec and was never encrypted (see the module docstring).
        """
        decoded: list[Payload] = []
        for payload in payloads:
            if payload.metadata.get("encoding") != ENCRYPTED_ENCODING:
                decoded.append(payload)
                continue
            decoded.append(self._decrypt_payload(payload))
        return decoded

    def _decrypt_payload(self, payload: Payload) -> Payload:
        """Decrypt one payload previously marked ``binary/encrypted``.

        Extracted from :meth:`decode` to isolate the per-payload error
        handling and bring the method under the length/complexity limits, per
        the Codacy review of this module. Behavior unchanged: raises
        :class:`PayloadCodecError` for every failure mode ``decode`` used to
        raise inline — unsupported algorithm, no keyring, unknown key id,
        truncated ciphertext, and a failed GCM authentication tag.
        """
        algorithm = payload.metadata.get(METADATA_ALGORITHM, b"")
        if algorithm != ALGORITHM:
            raise PayloadCodecError(
                "encrypted payload declares unsupported algorithm "
                f"'{algorithm.decode('utf-8', 'replace')}'; this process "
                f"implements {ALGORITHM.decode()} only."
            )

        key, key_id = self._resolve_decrypt_key(payload)
        return self._decrypt_ciphertext(payload.data, key, key_id)

    def _resolve_decrypt_key(self, payload: Payload) -> tuple[bytes, str]:
        """Look up the key this worker holds for ``payload``'s declared key id.

        Extracted from :meth:`decode`; behavior unchanged. Raises
        :class:`PayloadCodecError` when this process has no keyring at all,
        or when the declared key id is not one this process holds.
        """
        if self._keyring is None:
            raise PayloadCodecError(
                "received an encrypted Temporal payload but this process has "
                "no payload codec key. Provision "
                f"{PAYLOAD_CODEC_KEY_ENV} — plaintext passthrough "
                "cannot read encrypted history."
            )

        key_id = payload.metadata.get(METADATA_KEY_ID, b"").decode("utf-8", "replace")
        key = self._keyring.key_for(key_id)
        return key, key_id

    def _decrypt_ciphertext(self, raw: bytes, key: bytes, key_id: str) -> Payload:
        """Authenticate-decrypt one payload's wire bytes and parse the result.

        Extracted from :meth:`decode`; behavior unchanged.
        """
        plaintext = self._authenticate_and_decrypt(raw, key, key_id)
        return self._parse_decrypted_payload(plaintext, key_id)

    @staticmethod
    def _authenticate_and_decrypt(raw: bytes, key: bytes, key_id: str) -> bytes:
        """Split wire bytes into nonce/ciphertext and AES-GCM decrypt them.

        Extracted from :meth:`decode`; behavior unchanged. Raises
        :class:`PayloadCodecError` on truncated data or a failed GCM
        authentication tag.
        """
        if len(raw) <= NONCE_LENGTH_BYTES:
            raise PayloadCodecError(
                f"encrypted payload (key id '{key_id}') is truncated: "
                f"{len(raw)} bytes cannot hold a nonce plus ciphertext."
            )

        nonce, ciphertext = raw[:NONCE_LENGTH_BYTES], raw[NONCE_LENGTH_BYTES:]
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise PayloadCodecError(
                f"encrypted payload (key id '{key_id}') failed its "
                "authentication tag. The ciphertext was modified or the key "
                "under that id is not the key that encrypted it."
            ) from exc

    @staticmethod
    def _parse_decrypted_payload(plaintext: bytes, key_id: str) -> Payload:
        """Parse authenticated plaintext bytes as a Temporal ``Payload`` message.

        Extracted from :meth:`decode`; behavior unchanged for the happy path.
        Additionally wraps ``ParseFromString`` in the same fail-closed
        :class:`PayloadCodecError` contract: a GCM-authenticated plaintext
        that is not a valid ``Payload`` message (for example, from a
        version-skewed peer sharing this key) must not leak a raw
        ``google.protobuf.message.DecodeError`` — every other failure in this
        codec already raises :class:`PayloadCodecError`, and this one must
        match.
        """
        restored = Payload()
        try:
            restored.ParseFromString(plaintext)
        except DecodeError as exc:
            raise PayloadCodecError(
                f"encrypted payload (key id '{key_id}') authenticated "
                "successfully but its plaintext is not a valid Temporal "
                "Payload message; refusing to return corrupt data."
            ) from exc
        return restored


# --------------------------------------------------------------------------
# Data converter wiring
# --------------------------------------------------------------------------


def build_data_converter(
    codec: PayloadCodec | None = None,
) -> DataConverter:
    """Return the Adaptix ``DataConverter``: SDK defaults plus this codec.

    Only the codec slot is replaced. The default payload converter and failure
    converter are kept so JSON/proto/binary values, and Temporal's own failure
    shapes, continue to serialise exactly as they always have — the bytes are
    simply encrypted afterwards.

    Passing ``codec`` explicitly is for tests; production callers omit it and
    get :meth:`EncryptionPayloadCodec.from_environment`, which fails closed.
    """
    return dataclasses.replace(
        DataConverter.default,
        payload_codec=codec
        if codec is not None
        else EncryptionPayloadCodec.from_environment(),
    )
