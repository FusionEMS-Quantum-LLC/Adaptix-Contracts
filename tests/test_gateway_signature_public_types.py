from __future__ import annotations

import ast
import inspect
from typing import get_type_hints

from adaptix_contracts.auth import module_entitlement_gate
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


def test_gateway_emitted_session_claims_are_optional_payload_keys() -> None:
    # The gateway's own producer always emits both; neither is required of
    # contexts minted through GatewayClaims, which models neither.
    assert {"session_jti", "module_entitlements"} <= (
        VerifiedGatewayPayload.__optional_keys__
    )


def test_entitlement_gate_reads_only_declared_payload_keys() -> None:
    # Regression for the 5.46.0 Qodana High (PyTypedDictInspection): the gate
    # read ``module_entitlements`` off a VerifiedGatewayPayload that did not
    # declare it. Every literal key the gate reads off the verified payload
    # must be one the TypedDict declares.
    tree = ast.parse(inspect.getsource(module_entitlement_gate))
    read_keys = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "payload"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }

    assert "module_entitlements" in read_keys
    assert read_keys <= set(VerifiedGatewayPayload.__annotations__)
