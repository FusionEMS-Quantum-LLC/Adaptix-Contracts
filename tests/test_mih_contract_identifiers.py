from adaptix_contracts.mih import MIH_ENTITLEMENT_ID, MIH_SERVICE_AUDIENCE
from adaptix_contracts.service_audiences import KNOWN_SERVICE_AUDIENCES


def test_mih_contract_identifiers_are_canonical() -> None:
    assert MIH_ENTITLEMENT_ID == "mih_community_paramedicine"
    assert MIH_SERVICE_AUDIENCE == "adaptix-mih"
    assert MIH_SERVICE_AUDIENCE in KNOWN_SERVICE_AUDIENCES
