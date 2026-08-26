from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from adaptix_contracts.interoperability import (
    ShareDirection,
    SharePolicy,
    TrustDirection,
    TrustRelationship,
    TrustStatus,
)


def test_trust_and_disclosure_policy_are_separate_contracts() -> None:
    trust = TrustRelationship(
        trust_id="TRUST-1",
        peer_id="PEER-1",
        trust_direction=TrustDirection.BIDIRECTIONAL,
        status=TrustStatus.ACTIVE,
        allowed_purposes=("TREATMENT",),
        allowed_resource_types=("patient_encounter_summary",),
    )
    policy = SharePolicy(
        sharing_policy_id="POL-1",
        name="Clinical continuity",
        peer_id="PEER-1",
        resource_type="patient_encounter_summary",
        purpose_of_use="TREATMENT",
        direction=ShareDirection.BOTH,
        require_patient_match=True,
        require_consent=True,
    )

    assert trust.status is TrustStatus.ACTIVE
    assert policy.require_consent is True
    assert policy.require_patient_match is True


def test_invalid_trust_window_rejected() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        TrustRelationship(
            trust_id="TRUST-1",
            peer_id="PEER-1",
            trust_direction=TrustDirection.OUTBOUND,
            status=TrustStatus.ACTIVE,
            valid_from=now,
            valid_until=now - timedelta(seconds=1),
        )
