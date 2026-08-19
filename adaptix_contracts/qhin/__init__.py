"""Adaptix TEFCA QHIN Sub-Participant contracts (Play P26).

Re-exports the models, enums, event names/payloads/envelope factories,
and service error contracts for the QHIN-Service (TEFCA sub-participant
client + FHIR bidirectional exchange).
"""

from adaptix_contracts.qhin.enums import FhirVersion, Qhin, QhinPurpose
from adaptix_contracts.qhin.errors import (
    QhinErrorCode,
    QhinErrorEnvelope,
    QhinServiceError,
    credential_not_found,
    credential_purpose_not_authorized,
    qhin_unavailable,
    to_adaptix_error_code,
    transaction_not_found,
)
from adaptix_contracts.qhin.events import (
    QHIN_ACKNOWLEDGMENT_RECEIVED,
    QHIN_BUNDLE_PUBLISHED,
    QHIN_BUNDLE_RECEIVED,
    QHIN_EVENTS,
    QHIN_SOURCE_SERVICE,
    QHIN_TRANSACTION_COMPLETED,
    QHIN_TRANSACTION_STARTED,
    QhinAcknowledgmentReceivedPayload,
    QhinBundlePublishedPayload,
    QhinBundleReceivedPayload,
    QhinTransactionCompletedPayload,
    QhinTransactionStartedPayload,
    build_qhin_acknowledgment_received_event,
    build_qhin_bundle_published_event,
    build_qhin_bundle_received_event,
    build_qhin_transaction_completed_event,
    build_qhin_transaction_started_event,
)
from adaptix_contracts.qhin.models import (
    OutboundBundle,
    PatientBundle,
    QhinAcknowledgment,
    QhinCredential,
    QhinTransaction,
)

__all__ = [
    "FhirVersion",
    "OutboundBundle",
    "PatientBundle",
    "QHIN_ACKNOWLEDGMENT_RECEIVED",
    "QHIN_BUNDLE_PUBLISHED",
    "QHIN_BUNDLE_RECEIVED",
    "QHIN_EVENTS",
    "QHIN_SOURCE_SERVICE",
    "QHIN_TRANSACTION_COMPLETED",
    "QHIN_TRANSACTION_STARTED",
    "Qhin",
    "QhinAcknowledgment",
    "QhinAcknowledgmentReceivedPayload",
    "QhinBundlePublishedPayload",
    "QhinBundleReceivedPayload",
    "QhinCredential",
    "QhinErrorCode",
    "QhinErrorEnvelope",
    "QhinPurpose",
    "QhinServiceError",
    "QhinTransaction",
    "QhinTransactionCompletedPayload",
    "QhinTransactionStartedPayload",
    "build_qhin_acknowledgment_received_event",
    "build_qhin_bundle_published_event",
    "build_qhin_bundle_received_event",
    "build_qhin_transaction_completed_event",
    "build_qhin_transaction_started_event",
    "credential_not_found",
    "credential_purpose_not_authorized",
    "qhin_unavailable",
    "to_adaptix_error_code",
    "transaction_not_found",
]
