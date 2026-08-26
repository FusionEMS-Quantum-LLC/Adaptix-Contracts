from adaptix_contracts.service_audiences import KNOWN_SERVICE_AUDIENCES, is_known_service_audience


def test_qhin_service_audience_is_canonical() -> None:
    assert "adaptix-qhin" in KNOWN_SERVICE_AUDIENCES
    assert is_known_service_audience("adaptix-qhin")
