from adaptix_contracts.events.operational_envelope import OperationalEventEnvelope
from adaptix_contracts.interoperability import PublicSafetyExchangeEnvelope


def test_new_exchange_contract_does_not_replace_operational_event_envelope() -> None:
    assert OperationalEventEnvelope is not PublicSafetyExchangeEnvelope
    assert "payload" in OperationalEventEnvelope.model_fields
    assert "payload_ref" in PublicSafetyExchangeEnvelope.model_fields
