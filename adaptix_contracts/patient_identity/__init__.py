"""Patient-Identity domain contracts package.

Canonical home for contracts produced by Adaptix-Patient-Identity-Service.
"""

from adaptix_contracts.patient_identity.events import (
    PATIENT_IDENTITY_SOURCE_SERVICE,
    PATIENT_NOK_CONSENT_CHANGED,
    PatientNokConsentChangedPayload,
)

__all__ = [
    "PATIENT_IDENTITY_SOURCE_SERVICE",
    "PATIENT_NOK_CONSENT_CHANGED",
    "PatientNokConsentChangedPayload",
]
