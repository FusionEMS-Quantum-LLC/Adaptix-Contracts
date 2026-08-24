"""Shared Temporal contracts — the canonical payload codec and its wiring.

Import from here, never from a service-local copy::

    from adaptix_contracts.temporal import build_data_converter

    client = await Client.connect(host, namespace=ns,
                                  data_converter=build_data_converter())

WHY THIS LIVES IN CONTRACTS. The payload codec defines a cryptographic wire
format, and more than one process has to agree on it. A Temporal WORKER decodes
history, but the payload of a workflow's initial arguments is encoded by the
STARTING CLIENT's data converter — which belongs to whichever service called
``start_workflow``. A worker-side rollout therefore does not encrypt what a
starting client already wrote: that side has to attach the same converter
itself.

Two copies of that format that drift apart mean history written by one side
stops decoding on the other, on a store that must stay replayable for the life
of every open workflow. So there is exactly one definition and both sides
import it.

Requires the ``temporal`` extra::

    pip install "adaptix-contracts[temporal]"

Importing this package without ``temporalio`` installed raises ImportError with
that instruction, rather than failing later at an unrelated call site.
"""

from __future__ import annotations

try:
    from adaptix_contracts.temporal.codec import (
        ALGORITHM,
        ENCRYPTED_ENCODING,
        ENVIRONMENT_ENV,
        KEY_LENGTH_BYTES,
        METADATA_ALGORITHM,
        METADATA_KEY_ID,
        NONCE_LENGTH_BYTES,
        PAYLOAD_CODEC_KEY_ENV,
        PAYLOAD_CODEC_PLAINTEXT_ENV,
        PRODUCTION_ENVIRONMENTS,
        EncryptionPayloadCodec,
        Keyring,
        PayloadCodecError,
        build_data_converter,
        env_flag_is_true,
        is_production_environment,
    )
except ImportError as exc:  # pragma: no cover - exercised by the extras check
    raise ImportError(
        "adaptix_contracts.temporal requires the 'temporal' extra. "
        "Install with: pip install 'adaptix-contracts[temporal]'"
    ) from exc

__all__ = [
    "ALGORITHM",
    "ENCRYPTED_ENCODING",
    "ENVIRONMENT_ENV",
    "KEY_LENGTH_BYTES",
    "METADATA_ALGORITHM",
    "METADATA_KEY_ID",
    "NONCE_LENGTH_BYTES",
    "PAYLOAD_CODEC_KEY_ENV",
    "PAYLOAD_CODEC_PLAINTEXT_ENV",
    "PRODUCTION_ENVIRONMENTS",
    "EncryptionPayloadCodec",
    "Keyring",
    "PayloadCodecError",
    "build_data_converter",
    "env_flag_is_true",
    "is_production_environment",
]
