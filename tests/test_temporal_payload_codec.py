"""Tests for ``adaptix_contracts.security.temporal_payload_codec``.

Covers, in order:
  1. Keyring parsing (both accepted secret shapes) and its failure modes.
  2. Round-trip encode/decode, including key rotation and legacy passthrough.
  3. Fail-closed behaviour: construction, ``from_environment``, and the
     production plaintext refusal.
  4. ``build_data_converter`` wiring.
  5. Golden-vector interop with ``Adaptix-Temporal-Service``'s own codec
     (``backend/temporal_app/codec.py``) — the part that actually matters:
     proof this module reads and writes the identical wire format that repo
     has run in production since 2026-08-16 (PR #51).

None of the keys or ciphertexts below are real secrets. They are synthetic,
deterministic values (``bytes(range(32))``-style key material, a fixed
all-zero-to-eleven nonce) generated once, locally, for this test suite. This
repository is public; nothing here should ever be mistaken for — or replaced
with — real deployed key material.
"""

from __future__ import annotations

import base64
import os

import pytest
from temporalio.api.common.v1 import Payload
from temporalio.converter import DataConverter

from adaptix_contracts.security.temporal_payload_codec import (
    ALGORITHM,
    ENCRYPTED_ENCODING,
    ENVIRONMENT_ENV,
    METADATA_ALGORITHM,
    METADATA_KEY_ID,
    NONCE_LENGTH_BYTES,
    PAYLOAD_CODEC_KEY_ENV,
    PAYLOAD_CODEC_PLAINTEXT_ENV,
    EncryptionPayloadCodec,
    Keyring,
    PayloadCodecError,
    build_data_converter,
    env_flag_is_true,
    is_production_environment,
)

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — this repo's
# pytest.ini_options sets `asyncio_mode = "auto"` (see pyproject.toml), which
# auto-detects `async def` test functions without the marker. Applying the
# marker at module scope would tag the synchronous test functions below too
# and pytest-asyncio warns on exactly that.

# ---------------------------------------------------------------------------
# Synthetic test key material — NOT real secrets.
# ---------------------------------------------------------------------------

_KEY_A = bytes(range(32))
_KEY_B = bytes(range(32, 64))
_KEY_A_B64 = base64.b64encode(_KEY_A).decode()
_KEY_B_B64 = base64.b64encode(_KEY_B).decode()

_KEYRING_SECRET_ONE_KEY = (
    '{"primary_key_id": "k1", "keys": {"k1": "%s"}}' % _KEY_A_B64
)
_KEYRING_SECRET_TWO_KEYS_K1_PRIMARY = (
    '{"primary_key_id": "k1", "keys": {"k1": "%s", "k2": "%s"}}'
    % (_KEY_A_B64, _KEY_B_B64)
)
_KEYRING_SECRET_TWO_KEYS_K2_PRIMARY = (
    '{"primary_key_id": "k2", "keys": {"k1": "%s", "k2": "%s"}}'
    % (_KEY_A_B64, _KEY_B_B64)
)


def _sample_payload(data: bytes = b'"hello"') -> Payload:
    return Payload(metadata={"encoding": b"json/plain"}, data=data)


# ---------------------------------------------------------------------------
# Keyring parsing
# ---------------------------------------------------------------------------


class TestKeyringFromSecretValue:
    def test_keyring_json_shape(self) -> None:
        keyring = Keyring.from_secret_value(_KEYRING_SECRET_TWO_KEYS_K1_PRIMARY)
        assert keyring.primary_key_id == "k1"
        assert keyring.primary_key == _KEY_A
        assert keyring.key_for("k1") == _KEY_A
        assert keyring.key_for("k2") == _KEY_B

    def test_bare_base64_key_shape_derives_stable_id(self) -> None:
        import hashlib

        keyring = Keyring.from_secret_value(_KEY_A_B64)
        expected_id = hashlib.sha256(_KEY_A).hexdigest()[:16]
        assert keyring.primary_key_id == expected_id
        assert keyring.keys == {expected_id: _KEY_A}

    def test_bare_key_derivation_is_deterministic_across_instances(self) -> None:
        """Two independent parses of the same bare key must agree on its id.

        This is the property that makes a bare key usable between two
        different processes (e.g. a client and a worker) at all: if this
        module and its consumer disagreed on the derived id, each side would
        tag its own payloads with an id the other cannot look up.
        """
        first = Keyring.from_secret_value(_KEY_A_B64)
        second = Keyring.from_secret_value(_KEY_A_B64)
        assert first.primary_key_id == second.primary_key_id

    def test_empty_secret_raises(self) -> None:
        with pytest.raises(PayloadCodecError, match="empty"):
            Keyring.from_secret_value("")

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(PayloadCodecError, match="not valid JSON"):
            Keyring.from_secret_value("{not json")

    def test_json_missing_keys_object_raises(self) -> None:
        with pytest.raises(PayloadCodecError, match="'keys'"):
            Keyring.from_secret_value('{"primary_key_id": "k1"}')

    def test_json_missing_primary_key_id_raises(self) -> None:
        with pytest.raises(PayloadCodecError, match="primary_key_id"):
            Keyring.from_secret_value('{"keys": {"k1": "%s"}}' % _KEY_A_B64)

    def test_json_primary_key_id_not_in_keys_raises(self) -> None:
        with pytest.raises(PayloadCodecError, match="not present in its own key set"):
            Keyring.from_secret_value(
                '{"primary_key_id": "missing", "keys": {"k1": "%s"}}' % _KEY_A_B64
            )

    def test_wrong_length_key_raises(self) -> None:
        short_b64 = base64.b64encode(b"too-short").decode()
        with pytest.raises(PayloadCodecError, match="32 bytes"):
            Keyring.from_secret_value(
                '{"primary_key_id": "k1", "keys": {"k1": "%s"}}' % short_b64
            )

    def test_invalid_base64_raises(self) -> None:
        with pytest.raises(PayloadCodecError, match="not valid base64"):
            Keyring.from_secret_value(
                '{"primary_key_id": "k1", "keys": {"k1": "not-base64!!!"}}'
            )

    def test_error_messages_never_contain_key_material(self) -> None:
        """The key VALUE must never leak into an exception message."""
        secret = '{"primary_key_id": "k1", "keys": {"k1": "not-base64!!!"}}'
        with pytest.raises(PayloadCodecError) as excinfo:
            Keyring.from_secret_value(secret)
        assert "not-base64" not in str(excinfo.value)
        assert _KEY_A_B64 not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Round-trip encode/decode
# ---------------------------------------------------------------------------


class TestRoundTrip:
    async def test_round_trip_keyring_json(self) -> None:
        keyring = Keyring.from_secret_value(_KEYRING_SECRET_ONE_KEY)
        codec = EncryptionPayloadCodec(keyring)
        original = _sample_payload(b'"claim-123"')

        encoded = await codec.encode([original])
        assert encoded[0].metadata["encoding"] == ENCRYPTED_ENCODING
        assert encoded[0].metadata[METADATA_KEY_ID] == b"k1"
        assert encoded[0].metadata[METADATA_ALGORITHM] == ALGORITHM
        assert len(encoded[0].data) > NONCE_LENGTH_BYTES

        decoded = await codec.decode(encoded)
        assert decoded[0].SerializeToString() == original.SerializeToString()

    async def test_round_trip_bare_key(self) -> None:
        keyring = Keyring.from_secret_value(_KEY_A_B64)
        codec = EncryptionPayloadCodec(keyring)
        original = _sample_payload(b'"tenant-456"')

        encoded = await codec.encode([original])
        decoded = await codec.decode(encoded)
        assert decoded[0].SerializeToString() == original.SerializeToString()

    async def test_round_trip_multiple_payloads_in_one_call(self) -> None:
        keyring = Keyring.from_secret_value(_KEYRING_SECRET_ONE_KEY)
        codec = EncryptionPayloadCodec(keyring)
        originals = [_sample_payload(f'"item-{i}"'.encode()) for i in range(5)]

        encoded = await codec.encode(originals)
        decoded = await codec.decode(encoded)
        assert [p.SerializeToString() for p in decoded] == [
            p.SerializeToString() for p in originals
        ]
        # Each payload gets its own fresh nonce; ciphertexts must differ even
        # though several share a common prefix in their plaintext.
        assert len({p.data for p in encoded}) == len(encoded)

    async def test_key_rotation_new_primary_still_decodes_old_ciphertext(self) -> None:
        """Retiring key k1 in favour of k2 must not break history k1 wrote."""
        old_codec = EncryptionPayloadCodec(
            Keyring.from_secret_value(_KEYRING_SECRET_TWO_KEYS_K1_PRIMARY)
        )
        original = _sample_payload(b'"pre-rotation"')
        encoded_under_k1 = await old_codec.encode([original])
        assert encoded_under_k1[0].metadata[METADATA_KEY_ID] == b"k1"

        rotated_codec = EncryptionPayloadCodec(
            Keyring.from_secret_value(_KEYRING_SECRET_TWO_KEYS_K2_PRIMARY)
        )
        decoded = await rotated_codec.decode(encoded_under_k1)
        assert decoded[0].SerializeToString() == original.SerializeToString()

        # New encryption under the rotated codec now uses k2.
        encoded_under_k2 = await rotated_codec.encode([original])
        assert encoded_under_k2[0].metadata[METADATA_KEY_ID] == b"k2"

    async def test_decode_passes_through_unmarked_legacy_payload(self) -> None:
        """A payload with no encrypted marker predates codec adoption.

        Decode must return it byte-for-byte unchanged — this is what keeps
        pre-existing plaintext workflow history replayable.
        """
        keyring = Keyring.from_secret_value(_KEYRING_SECRET_ONE_KEY)
        codec = EncryptionPayloadCodec(keyring)
        legacy = Payload(metadata={"encoding": b"json/plain"}, data=b'"legacy"')

        decoded = await codec.decode([legacy])
        assert decoded[0].SerializeToString() == legacy.SerializeToString()

    async def test_decode_unknown_key_id_raises(self) -> None:
        writer = EncryptionPayloadCodec(Keyring.from_secret_value(_KEYRING_SECRET_ONE_KEY))
        encoded = await writer.encode([_sample_payload()])

        reader = EncryptionPayloadCodec(Keyring.from_secret_value(_KEY_B_B64))
        with pytest.raises(PayloadCodecError, match="does not hold"):
            await reader.decode(encoded)

    async def test_decode_tampered_ciphertext_raises(self) -> None:
        keyring = Keyring.from_secret_value(_KEYRING_SECRET_ONE_KEY)
        codec = EncryptionPayloadCodec(keyring)
        encoded = await codec.encode([_sample_payload()])

        tampered_data = bytearray(encoded[0].data)
        tampered_data[-1] ^= 0xFF
        tampered = Payload(metadata=dict(encoded[0].metadata), data=bytes(tampered_data))

        with pytest.raises(PayloadCodecError, match="authentication tag"):
            await codec.decode([tampered])

    async def test_decode_truncated_payload_raises(self) -> None:
        keyring = Keyring.from_secret_value(_KEYRING_SECRET_ONE_KEY)
        codec = EncryptionPayloadCodec(keyring)
        truncated = Payload(
            metadata={
                "encoding": ENCRYPTED_ENCODING,
                METADATA_KEY_ID: b"k1",
                METADATA_ALGORITHM: ALGORITHM,
            },
            data=b"\x00" * 4,
        )
        with pytest.raises(PayloadCodecError, match="truncated"):
            await codec.decode([truncated])

    async def test_decode_unsupported_algorithm_raises(self) -> None:
        keyring = Keyring.from_secret_value(_KEYRING_SECRET_ONE_KEY)
        codec = EncryptionPayloadCodec(keyring)
        bogus = Payload(
            metadata={
                "encoding": ENCRYPTED_ENCODING,
                METADATA_KEY_ID: b"k1",
                METADATA_ALGORITHM: b"AES-128-CBC",
            },
            data=b"\x00" * 32,
        )
        with pytest.raises(PayloadCodecError, match="unsupported algorithm"):
            await codec.decode([bogus])

    async def test_decode_encrypted_payload_with_no_keyring_raises(self) -> None:
        codec = EncryptionPayloadCodec(None, plaintext_passthrough=True)
        marked = Payload(
            metadata={
                "encoding": ENCRYPTED_ENCODING,
                METADATA_KEY_ID: b"k1",
                METADATA_ALGORITHM: ALGORITHM,
            },
            data=b"\x00" * 32,
        )
        with pytest.raises(PayloadCodecError, match="no payload codec key"):
            await codec.decode([marked])


# ---------------------------------------------------------------------------
# Fail-closed construction and environment wiring
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_constructor_requires_keyring_unless_plaintext_explicit(self) -> None:
        with pytest.raises(PayloadCodecError, match="requires a keyring"):
            EncryptionPayloadCodec(None)

    def test_constructor_allows_none_keyring_with_explicit_flag(self) -> None:
        codec = EncryptionPayloadCodec(None, plaintext_passthrough=True)
        assert codec.is_encrypting is False
        assert codec.primary_key_id is None

    async def test_encode_passthrough_only_in_explicit_plaintext_mode(self) -> None:
        codec = EncryptionPayloadCodec(None, plaintext_passthrough=True)
        original = _sample_payload()
        encoded = await codec.encode([original])
        assert encoded[0].SerializeToString() == original.SerializeToString()

    def test_from_environment_no_key_no_flag_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(PAYLOAD_CODEC_KEY_ENV, raising=False)
        monkeypatch.delenv(PAYLOAD_CODEC_PLAINTEXT_ENV, raising=False)
        monkeypatch.setenv(ENVIRONMENT_ENV, "test")
        with pytest.raises(PayloadCodecError, match="is not configured"):
            EncryptionPayloadCodec.from_environment()

    def test_from_environment_plaintext_flag_refused_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(PAYLOAD_CODEC_KEY_ENV, raising=False)
        monkeypatch.setenv(PAYLOAD_CODEC_PLAINTEXT_ENV, "true")
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")
        with pytest.raises(PayloadCodecError, match="never permitted in production"):
            EncryptionPayloadCodec.from_environment()

    @pytest.mark.parametrize("prod_name", ["production", "PROD", " Production "])
    def test_production_detection_is_case_and_whitespace_tolerant(
        self, monkeypatch: pytest.MonkeyPatch, prod_name: str
    ) -> None:
        monkeypatch.delenv(PAYLOAD_CODEC_KEY_ENV, raising=False)
        monkeypatch.setenv(PAYLOAD_CODEC_PLAINTEXT_ENV, "true")
        monkeypatch.setenv(ENVIRONMENT_ENV, prod_name)
        with pytest.raises(PayloadCodecError, match="production"):
            EncryptionPayloadCodec.from_environment()

    def test_from_environment_plaintext_flag_allowed_outside_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(PAYLOAD_CODEC_KEY_ENV, raising=False)
        monkeypatch.setenv(PAYLOAD_CODEC_PLAINTEXT_ENV, "true")
        monkeypatch.setenv(ENVIRONMENT_ENV, "local")
        codec = EncryptionPayloadCodec.from_environment()
        assert codec.is_encrypting is False

    def test_from_environment_builds_encrypting_codec_from_keyring_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(PAYLOAD_CODEC_KEY_ENV, _KEYRING_SECRET_ONE_KEY)
        monkeypatch.delenv(PAYLOAD_CODEC_PLAINTEXT_ENV, raising=False)
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")
        codec = EncryptionPayloadCodec.from_environment()
        assert codec.is_encrypting is True
        assert codec.primary_key_id == "k1"

    def test_from_environment_builds_encrypting_codec_from_bare_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(PAYLOAD_CODEC_KEY_ENV, _KEY_A_B64)
        monkeypatch.delenv(PAYLOAD_CODEC_PLAINTEXT_ENV, raising=False)
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")
        codec = EncryptionPayloadCodec.from_environment()
        assert codec.is_encrypting is True

    def test_key_takes_precedence_over_plaintext_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A key configured alongside the local flag still encrypts.

        The plaintext escape hatch is for when there is NO key at all; a
        real key present must always win.
        """
        monkeypatch.setenv(PAYLOAD_CODEC_KEY_ENV, _KEYRING_SECRET_ONE_KEY)
        monkeypatch.setenv(PAYLOAD_CODEC_PLAINTEXT_ENV, "true")
        monkeypatch.setenv(ENVIRONMENT_ENV, "local")
        codec = EncryptionPayloadCodec.from_environment()
        assert codec.is_encrypting is True


class TestEnvFlagHelpers:
    @pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on", " TRUE "])
    def test_env_flag_true_values(self, value: str) -> None:
        assert env_flag_is_true(value) is True

    @pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off", "garbage"])
    def test_env_flag_false_values(self, value: str | None) -> None:
        assert env_flag_is_true(value) is False

    @pytest.mark.parametrize("value", ["production", "prod", "PROD", " Production "])
    def test_is_production_environment_true(self, value: str) -> None:
        assert is_production_environment(value) is True

    @pytest.mark.parametrize("value", [None, "", "staging", "local", "test", "development"])
    def test_is_production_environment_false(self, value: str | None) -> None:
        assert is_production_environment(value) is False


# ---------------------------------------------------------------------------
# DataConverter wiring
# ---------------------------------------------------------------------------


class TestBuildDataConverter:
    def test_explicit_codec_is_used_without_touching_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No env configured at all — if build_data_converter fell back to
        # from_environment() despite receiving an explicit codec, this would
        # raise PayloadCodecError and fail the test.
        monkeypatch.delenv(PAYLOAD_CODEC_KEY_ENV, raising=False)
        monkeypatch.delenv(PAYLOAD_CODEC_PLAINTEXT_ENV, raising=False)
        codec = EncryptionPayloadCodec(None, plaintext_passthrough=True)

        converter = build_data_converter(codec)

        assert converter.payload_codec is codec
        # Everything else stays the SDK default.
        assert converter.payload_converter_class is DataConverter.default.payload_converter_class
        assert converter.failure_converter_class is DataConverter.default.failure_converter_class

    def test_omitted_codec_falls_back_to_from_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(PAYLOAD_CODEC_KEY_ENV, _KEYRING_SECRET_ONE_KEY)
        monkeypatch.delenv(PAYLOAD_CODEC_PLAINTEXT_ENV, raising=False)
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")

        converter = build_data_converter()

        assert isinstance(converter.payload_codec, EncryptionPayloadCodec)
        assert converter.payload_codec.is_encrypting is True

    def test_omitted_codec_fails_closed_when_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(PAYLOAD_CODEC_KEY_ENV, raising=False)
        monkeypatch.delenv(PAYLOAD_CODEC_PLAINTEXT_ENV, raising=False)
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")
        with pytest.raises(PayloadCodecError):
            build_data_converter()


# ---------------------------------------------------------------------------
# Golden-vector interop with Adaptix-Temporal-Service's own codec
#
# Generated once, locally, by running BOTH codecs side by side against the
# same synthetic key material and a fixed (monkeypatched os.urandom) nonce:
#   - Adaptix-Temporal-Service backend/temporal_app/codec.py
#     @ commit 5de9ee9f955e6d4619a35f1e24b077fb25fe4119 (2026-08-24, HEAD of
#     main at verification time; the codec module itself was introduced by
#     that repo's PR #51 on 2026-08-16 and is unchanged since)
#   - this module (adaptix_contracts.security.temporal_payload_codec)
#
# The generation run asserted FOUR things live, in both directions, for both
# secret shapes (not just what is re-asserted below from the frozen bytes):
#   1. this module's decode() of Temporal-Service's encode() output recovers
#      the exact original inner Payload,
#   2. this module's encode() of the same input, key, and nonce is
#      BYTE-IDENTICAL (ciphertext AND metadata) to Temporal-Service's own
#      encode() output,
#   3. Temporal-Service's own codec successfully decodes THIS module's
#      encode() output back to the exact original inner Payload, and
#   4. the derived key id for a bare base64 key matches on both sides.
# All four passed. What is committed here is the golden-vector half of that
# proof (1) plus the byte-identical re-encode half (2) — the two properties
# a CI run in THIS repository can check without a runtime dependency on
# Adaptix-Temporal-Service. Property (3) cannot be re-checked without that
# repository's code present, but is implied by (1)+(2): if this module's
# encode() output is byte-identical to Temporal-Service's, and
# Temporal-Service can decode its own output (trivially true — this module's
# round-trip tests above and Temporal-Service's own test suite both prove
# that independently), then it can decode this module's output too.
# ---------------------------------------------------------------------------


class TestGoldenVectorInteropWithTemporalService:
    # -- Case 1: production keyring-JSON secret shape ----------------------
    _KEYRING_SECRET = (
        '{"primary_key_id": "test-2026-08", '
        '"keys": {"test-2026-08": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="}}'
    )
    _KEYRING_PRIMARY_KEY_ID = "test-2026-08"
    _KEYRING_INNER_METADATA = {"encoding": b"json/plain"}
    _KEYRING_INNER_DATA = b'"claim-golden-vector-abc123"'
    _KEYRING_FIXED_NONCE = bytes(range(12))
    _KEYRING_CIPHERTEXT_HEX = (
        "000102030405060708090a0b4d14dc13a08ba174e928f9eca3e3121eecb8a8"
        "449c1a36122a7bc7e6710869df2c77c190cba47cb502c11c99e7f505598c3a"
        "51bf69f4e5e14734d2d3b05df480f2859eede0e3"
    )
    _KEYRING_OUTER_METADATA = {
        "encryption-algorithm": b"AES-256-GCM",
        "encryption-key-id": b"test-2026-08",
        "encoding": b"binary/encrypted",
    }

    # -- Case 2: bare base64 local-development secret shape -----------------
    _BARE_SECRET = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
    _BARE_PRIMARY_KEY_ID = "ae216c2ef5247a37"
    _BARE_INNER_METADATA = {"encoding": b"json/plain"}
    _BARE_INNER_DATA = b'"tenant-golden-vector-xyz789"'
    _BARE_FIXED_NONCE = bytes(range(12))
    _BARE_CIPHERTEXT_HEX = (
        "000102030405060708090a0b7b260b9fadb302646b42dc2676929dfe46f992"
        "e512fe1312df555fc939bb5355f285d58f2be19c4f1a256a4ec658c7631b65"
        "9a99aaf3774ad1acfffe3191e0883d56bae32a7a84"
    )
    _BARE_OUTER_METADATA = {
        "encryption-algorithm": b"AES-256-GCM",
        "encryption-key-id": b"ae216c2ef5247a37",
        "encoding": b"binary/encrypted",
    }

    async def test_decodes_temporal_service_keyring_json_ciphertext(self) -> None:
        keyring = Keyring.from_secret_value(self._KEYRING_SECRET)
        assert keyring.primary_key_id == self._KEYRING_PRIMARY_KEY_ID
        codec = EncryptionPayloadCodec(keyring)

        outer = Payload(
            metadata=self._KEYRING_OUTER_METADATA,
            data=bytes.fromhex(self._KEYRING_CIPHERTEXT_HEX),
        )
        decoded = await codec.decode([outer])

        assert dict(decoded[0].metadata) == self._KEYRING_INNER_METADATA
        assert decoded[0].data == self._KEYRING_INNER_DATA

    async def test_encode_reproduces_temporal_service_keyring_json_ciphertext(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        keyring = Keyring.from_secret_value(self._KEYRING_SECRET)
        codec = EncryptionPayloadCodec(keyring)
        inner = Payload(
            metadata=self._KEYRING_INNER_METADATA, data=self._KEYRING_INNER_DATA
        )

        monkeypatch.setattr(
            "adaptix_contracts.security.temporal_payload_codec.os.urandom",
            lambda n: self._KEYRING_FIXED_NONCE,
        )
        encoded = await codec.encode([inner])

        assert encoded[0].data == bytes.fromhex(self._KEYRING_CIPHERTEXT_HEX)
        assert dict(encoded[0].metadata) == self._KEYRING_OUTER_METADATA

    async def test_decodes_temporal_service_bare_key_ciphertext(self) -> None:
        keyring = Keyring.from_secret_value(self._BARE_SECRET)
        assert keyring.primary_key_id == self._BARE_PRIMARY_KEY_ID
        codec = EncryptionPayloadCodec(keyring)

        outer = Payload(
            metadata=self._BARE_OUTER_METADATA,
            data=bytes.fromhex(self._BARE_CIPHERTEXT_HEX),
        )
        decoded = await codec.decode([outer])

        assert dict(decoded[0].metadata) == self._BARE_INNER_METADATA
        assert decoded[0].data == self._BARE_INNER_DATA

    async def test_encode_reproduces_temporal_service_bare_key_ciphertext(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        keyring = Keyring.from_secret_value(self._BARE_SECRET)
        codec = EncryptionPayloadCodec(keyring)
        inner = Payload(metadata=self._BARE_INNER_METADATA, data=self._BARE_INNER_DATA)

        monkeypatch.setattr(
            "adaptix_contracts.security.temporal_payload_codec.os.urandom",
            lambda n: self._BARE_FIXED_NONCE,
        )
        encoded = await codec.encode([inner])

        assert encoded[0].data == bytes.fromhex(self._BARE_CIPHERTEXT_HEX)
        assert dict(encoded[0].metadata) == self._BARE_OUTER_METADATA
