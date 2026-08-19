"""Enums for the Adaptix QA (Chart Review / QI Workbench) service.

Chart review is the clinical quality-assurance workflow: a reviewer reads
a completed ePCR chart against a checklist, records findings, and rolls
findings up into CQI (continuous quality improvement) metrics.
"""

from __future__ import annotations

from enum import StrEnum


class ReviewOutcome(StrEnum):
    """Terminal outcome of a chart review.

    ``partial`` covers a review that found some checklist items
    non-compliant but not enough (or not severe enough) to fail the
    chart outright; the reviewer's findings determine which.
    """

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"


class FindingSeverity(StrEnum):
    """Severity of a single review finding.

    ``critical`` findings are the ones that can fail an otherwise
    passing review (e.g. a missing narcotic count, an undocumented
    refusal) and MUST be routed to the agency's clinical lead.
    """

    INFORMATIONAL = "informational"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class ReviewerRole(StrEnum):
    """Role of the person performing or assigned a chart review.

    ``peer`` is a same-level clinician review (crew-to-crew QA);
    ``medical_director`` and ``qi_coordinator`` are the roles with
    authority to close out a review and adjust CQI metrics.
    """

    PEER = "peer"
    SUPERVISOR = "supervisor"
    QI_COORDINATOR = "qi_coordinator"
    MEDICAL_DIRECTOR = "medical_director"


__all__ = [
    "FindingSeverity",
    "ReviewOutcome",
    "ReviewerRole",
]
