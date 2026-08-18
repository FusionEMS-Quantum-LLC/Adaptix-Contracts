"""Community Risk Reduction (CRR) + Vision 20/20 shared contracts (Play P08).

Re-exports the public surface of the ``adaptix_contracts.crr`` subpackage so
consumers can ``from adaptix_contracts.crr import CrrCampaign`` without knowing
the internal module split.
"""

from adaptix_contracts.crr.enums import (
    CrrOutcome,
    InterventionType,
)
from adaptix_contracts.crr.errors import (
    CrrCampaignAlreadyLaunchedError,
    CrrCampaignInvalidStateError,
    CrrCampaignNotFoundError,
    CrrError,
    CrrErrorCode,
    CrrHouseholdDuplicateError,
    CrrHouseholdNotFoundError,
    CrrInterventionMissingTargetError,
    CrrInterventionNotFoundError,
    CrrInterventionTypeUnsupportedError,
    CrrIsoPackageGenerationFailedError,
    CrrIsoPackageInsufficientEvidenceError,
    CrrOutcomeCohortNotFoundError,
    CrrOutcomeMeasurementWindowInvalidError,
)
from adaptix_contracts.crr.events import (
    CRR_CAMPAIGN_LAUNCHED,
    CRR_EVENTS,
    CRR_INTERVENTION_COMPLETED,
    CRR_OUTCOME_MEASURED,
    CrrCampaignLaunchedEvent,
    CrrInterventionCompletedEvent,
    CrrOutcomeMeasuredEvent,
    ISO_PACKAGE_GENERATED,
    IsoPackageGeneratedEvent,
)
from adaptix_contracts.crr.models import (
    CrrCampaign,
    Intervention,
    IsoCreditPackage,
    OutcomeCohort,
    TargetHousehold,
)

__all__ = [
    "CRR_CAMPAIGN_LAUNCHED",
    "CRR_EVENTS",
    "CRR_INTERVENTION_COMPLETED",
    "CRR_OUTCOME_MEASURED",
    "CrrCampaign",
    "CrrCampaignAlreadyLaunchedError",
    "CrrCampaignInvalidStateError",
    "CrrCampaignLaunchedEvent",
    "CrrCampaignNotFoundError",
    "CrrError",
    "CrrErrorCode",
    "CrrHouseholdDuplicateError",
    "CrrHouseholdNotFoundError",
    "CrrInterventionCompletedEvent",
    "CrrInterventionMissingTargetError",
    "CrrInterventionNotFoundError",
    "CrrInterventionTypeUnsupportedError",
    "CrrIsoPackageGenerationFailedError",
    "CrrIsoPackageInsufficientEvidenceError",
    "CrrOutcome",
    "CrrOutcomeCohortNotFoundError",
    "CrrOutcomeMeasuredEvent",
    "CrrOutcomeMeasurementWindowInvalidError",
    "ISO_PACKAGE_GENERATED",
    "Intervention",
    "InterventionType",
    "IsoCreditPackage",
    "IsoPackageGeneratedEvent",
    "OutcomeCohort",
    "TargetHousehold",
]
