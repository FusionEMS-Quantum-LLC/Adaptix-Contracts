from __future__ import annotations

from typing import get_type_hints

from adaptix_contracts.gateway_signature import (
    GatewayRequest,
    VerifiedGatewayPayload,
    verify_gateway_signature,
    verify_gateway_signature_for_request,
    verify_gateway_signature_without_request_binding,
)


def test_public_verifiers_return_verified_gateway_payload() -> None:
    verifiers = (
        verify_gateway_signature,
        verify_gateway_signature_for_request,
        verify_gateway_signature_without_request_binding,
    )

    for verifier in verifiers:
        assert get_type_hints(verifier)["return"] is VerifiedGatewayPayload


def test_request_verifier_uses_the_structural_gateway_request_protocol() -> None:
    assert (
        get_type_hints(verify_gateway_signature_for_request)["request"]
        == GatewayRequest | None
    )
