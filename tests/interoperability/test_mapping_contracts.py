from datetime import datetime, timezone

from adaptix_contracts.interoperability import MappingType, SemanticMappingRule


def test_no_equivalent_is_explicit_not_fabricated() -> None:
    rule = SemanticMappingRule(
        mapping_rule_id="R-CLINICAL-MED",
        mapping_set_id="PRODUCTION",
        source_standard="NEMSIS",
        source_version="3.5.1",
        source_path="eMedications.03",
        canonical_path="clinical.medication",
        target_standard="NERIS",
        target_version="supported",
        target_path=None,
        mapping_type=MappingType.NO_EQUIVALENT,
        confidence=1.0,
        effective_from=datetime.now(timezone.utc),
    )

    assert rule.mapping_type is MappingType.NO_EQUIVALENT
    assert rule.target_path is None
