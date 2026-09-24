"""Exchange gateway descriptor contract (FND-001).

Proves the ownership rule (an outside system is never a core prerequisite),
honest status, and the references a descriptor may and may not carry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from adaptix_contracts.interoperability.gateway import (
    ADAPTIX_OWNED_GATEWAY_KINDS,
    EXTERNAL_GATEWAY_KINDS,
    ExchangeGatewayDescriptor,
    ExchangeGatewayKind,
    ExchangeGatewayStatus,
    is_external_gateway_kind,
)
from adaptix_contracts.interoperability.trust import TrustDirection

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _gateway(**overrides: object) -> ExchangeGatewayDescriptor:
    data: dict[str, object] = {
        "gateway_id": "gw-1",
        "tenant_id": "tenant-cert-a",
        "kind": ExchangeGatewayKind.HOSPITAL_INTERFACE,
        "display_name": "Certification Regional Hospital interface",
        "status": ExchangeGatewayStatus.CONFIGURED,
        "direction": TrustDirection.BIDIRECTIONAL,
        "supported_resource_types": ("patient_encounter_summary",),
        "status_changed_at": NOW,
        "version": 1,
    }
    data.update(overrides)
    return ExchangeGatewayDescriptor.model_validate(data)


def test_gateway_kind_vocabulary_is_exactly_the_card() -> None:
    assert {kind.value for kind in ExchangeGatewayKind} == {
        "adaptix_peer",
        "hospital_interface",
        "fhir_api",
        "direct",
        "hie",
        "qhin",
        "regional_exchange",
        "state_system",
    }


def test_gateway_status_vocabulary_is_exactly_the_card() -> None:
    assert {status.value for status in ExchangeGatewayStatus} == {
        "CONFIGURED",
        "NOT_CONFIGURED",
        "DEGRADED",
        "DISABLED",
        "WAITING_EXTERNAL_CREDENTIAL",
    }


def test_only_adaptix_peer_is_adaptix_owned() -> None:
    assert ADAPTIX_OWNED_GATEWAY_KINDS == {ExchangeGatewayKind.ADAPTIX_PEER}
    assert EXTERNAL_GATEWAY_KINDS == set(ExchangeGatewayKind) - {
        ExchangeGatewayKind.ADAPTIX_PEER
    }


@pytest.mark.parametrize("kind", sorted(EXTERNAL_GATEWAY_KINDS, key=lambda k: k.value))
def test_external_gateway_must_be_optional(kind: ExchangeGatewayKind) -> None:
    extra = {"qhin_credential_id": uuid4()} if kind is ExchangeGatewayKind.QHIN else {}
    assert _gateway(kind=kind, **extra).optional is True
    with pytest.raises(ValidationError, match="must be optional=True"):
        _gateway(kind=kind, optional=False, **extra)


def test_external_gateway_defaults_to_optional() -> None:
    assert _gateway().optional is True


def test_adaptix_peer_may_be_required() -> None:
    gateway = _gateway(
        kind=ExchangeGatewayKind.ADAPTIX_PEER, optional=False, peer_id="peer-7"
    )
    assert gateway.optional is False


def test_adaptix_peer_never_waits_on_an_external_credential() -> None:
    with pytest.raises(ValidationError, match="never waits on an external credential"):
        _gateway(
            kind=ExchangeGatewayKind.ADAPTIX_PEER,
            peer_id="peer-7",
            status=ExchangeGatewayStatus.WAITING_EXTERNAL_CREDENTIAL,
            status_reason="waiting",
        )


def test_external_gateway_may_wait_on_an_external_credential() -> None:
    gateway = _gateway(
        kind=ExchangeGatewayKind.FHIR_API,
        status=ExchangeGatewayStatus.WAITING_EXTERNAL_CREDENTIAL,
        status_reason="client registration requested from the hospital",
    )
    assert gateway.status is ExchangeGatewayStatus.WAITING_EXTERNAL_CREDENTIAL


def test_adaptix_peer_names_its_peer() -> None:
    with pytest.raises(ValidationError, match="must name its peer_id"):
        _gateway(kind=ExchangeGatewayKind.ADAPTIX_PEER)


def test_only_a_qhin_gateway_carries_a_qhin_credential() -> None:
    with pytest.raises(ValidationError, match="only a qhin gateway"):
        _gateway(qhin_credential_id=uuid4())


@pytest.mark.parametrize(
    "status", [ExchangeGatewayStatus.CONFIGURED, ExchangeGatewayStatus.DEGRADED]
)
def test_a_usable_qhin_gateway_references_its_credential(
    status: ExchangeGatewayStatus,
) -> None:
    reason = None if status is ExchangeGatewayStatus.CONFIGURED else "slow responses"
    with pytest.raises(ValidationError, match="must reference its QhinCredential"):
        _gateway(kind=ExchangeGatewayKind.QHIN, status=status, status_reason=reason)


def test_a_not_configured_qhin_gateway_needs_no_credential() -> None:
    gateway = _gateway(
        kind=ExchangeGatewayKind.QHIN,
        status=ExchangeGatewayStatus.NOT_CONFIGURED,
        status_reason="no QHIN participation agreement for this tenant",
    )
    assert gateway.qhin_credential_id is None


@pytest.mark.parametrize(
    "status",
    [
        status
        for status in ExchangeGatewayStatus
        if status is not ExchangeGatewayStatus.CONFIGURED
    ],
)
def test_every_non_configured_status_states_its_reason(
    status: ExchangeGatewayStatus,
) -> None:
    with pytest.raises(ValidationError, match="must state its status_reason"):
        _gateway(status=status)


def test_unknown_kind_is_treated_as_external() -> None:
    assert is_external_gateway_kind("carrier_pigeon") is True
    assert is_external_gateway_kind("adaptix_peer") is False
    assert is_external_gateway_kind(ExchangeGatewayKind.HIE) is True


def test_descriptor_refuses_a_secret_field_and_naive_time_and_lax_version() -> None:
    with pytest.raises(ValidationError, match="extra"):
        _gateway(credential_value="synthetic-certification-value")
    with pytest.raises(ValidationError, match="timezone"):
        _gateway(status_changed_at=datetime(2026, 9, 24, 12, 0))
    with pytest.raises(ValidationError):
        _gateway(version=True)
    with pytest.raises(ValidationError):
        _gateway(version="2")
    with pytest.raises(ValidationError):
        _gateway(optional="false")


def test_descriptor_refuses_control_characters_in_references() -> None:
    with pytest.raises(ValidationError):
        _gateway(gateway_id="gw-1\r\nX-Injected: 1")


def test_descriptor_is_frozen() -> None:
    gateway = _gateway()
    with pytest.raises(ValidationError):
        setattr(gateway, "status", ExchangeGatewayStatus.DISABLED)


def test_descriptor_round_trips_through_json() -> None:
    gateway = _gateway()
    assert (
        ExchangeGatewayDescriptor.model_validate_json(gateway.model_dump_json())
        == gateway
    )
