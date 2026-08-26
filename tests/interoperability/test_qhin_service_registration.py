from adaptix_contracts.schemas.service_registry import QHIN_SERVICE, SERVICE_BY_SLUG
from adaptix_contracts.service_audiences import KNOWN_SERVICE_AUDIENCES


def test_qhin_service_is_registered_with_deploy_contract() -> None:
    assert SERVICE_BY_SLUG["qhin"] is QHIN_SERVICE
    assert QHIN_SERVICE.name == "Adaptix-QHIN-Service"
    assert QHIN_SERVICE.route_prefix == "/api/v1/qhin"
    assert QHIN_SERVICE.port == 8048
    assert QHIN_SERVICE.domain_owner is True


def test_qhin_gateway_audience_exists_for_registered_service() -> None:
    assert "adaptix-qhin" in KNOWN_SERVICE_AUDIENCES
