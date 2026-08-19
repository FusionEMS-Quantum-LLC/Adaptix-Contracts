"""Adaptix TEFCA QHIN Sub-Participant — Enumerations.

Play P26 (TEFCA sub-participant client + FHIR bidirectional exchange).
Enums are shared across ``models.py`` and ``events.py`` so QHIN identity,
FHIR version, and exchange purpose strings never drift between the models
a service publishes and the events consumers read.
"""

from __future__ import annotations

from enum import StrEnum


class Qhin(StrEnum):
    """Qualified Health Information Network the platform connects to as a
    TEFCA sub-participant.

    Values are the QHINs Josh named explicitly in Play P26.
    """

    HEALTH_GORILLA = "health_gorilla"
    KNO2 = "kno2"
    COMMONWELL = "commonwell"
    EHEALTH_EXCHANGE = "ehealth_exchange"
    EPIC_NEXUS = "epic_nexus"
    ORACLE_HEALTH = "oracle_health"
    MEDALLIES = "medallies"
    KONZA = "konza"
    NETSMART = "netsmart"
    SURESCRIPTS = "surescripts"
    ECLINICALWORKS = "eclinicalworks"


class FhirVersion(StrEnum):
    """FHIR version negotiated for a QHIN exchange."""

    R4 = "r4"
    R5 = "r5"


class QhinPurpose(StrEnum):
    """TEFCA Exchange Purpose asserted on a QHIN transaction.

    Mirrors the RCE-published Exchange Purposes so a transaction's asserted
    purpose can be validated against what the QHIN and the responding
    participant actually authorize.
    """

    TREATMENT = "treatment"
    IAS = "ias"
    PUBLIC_HEALTH = "public_health"
    HEALTHCARE_OPS = "healthcare_ops"
    PAYMENT = "payment"
    GOVT_BENEFITS = "govt_benefits"


__all__ = [
    "FhirVersion",
    "Qhin",
    "QhinPurpose",
]
