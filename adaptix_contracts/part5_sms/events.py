"""Event constants for Play P14 — Adaptix Part 5 SMS.

The five event types listed in the Play P14 contract:

- ``sms.hazard.reported`` — a new :class:`HazardReport` was filed.
- ``sms.risk.assessed`` — a :class:`RiskAssessment` was signed off.
- ``sms.mitigation.implemented`` — a :class:`Mitigation` reached the
  implemented state (evidence attached, but not yet verified effective).
- ``sms.audit.opened`` — an :class:`InternalAudit` transitioned to ``OPEN``.
- ``sms.corrective_action.closed`` — a :class:`CorrectiveAction` was closed
  by an owner with verification evidence attached.

Every constant is namespaced ``sms.*`` so it does not collide with the pre-
existing text-messaging ``communications`` events, and so a subscriber can
scope an EventBridge / SNS filter to the entire Part 5 SMS domain with a
single prefix rule.

Producer: Adaptix-Compliance-Service. Registration in the master event
registry (:mod:`adaptix_contracts.events.registry`) is a follow-up commit
that lands together with the service standing up an outbox — Part 5 SMS
consumers can already import the constants from this module today.
"""

from __future__ import annotations

from typing import Final

SMS_HAZARD_REPORTED: Final[str] = "sms.hazard.reported"
SMS_RISK_ASSESSED: Final[str] = "sms.risk.assessed"
SMS_MITIGATION_IMPLEMENTED: Final[str] = "sms.mitigation.implemented"
SMS_AUDIT_OPENED: Final[str] = "sms.audit.opened"
SMS_CORRECTIVE_ACTION_CLOSED: Final[str] = "sms.corrective_action.closed"

PART5_SMS_EVENTS: Final[frozenset[str]] = frozenset(
    {
        SMS_HAZARD_REPORTED,
        SMS_RISK_ASSESSED,
        SMS_MITIGATION_IMPLEMENTED,
        SMS_AUDIT_OPENED,
        SMS_CORRECTIVE_ACTION_CLOSED,
    }
)

__all__ = [
    "PART5_SMS_EVENTS",
    "SMS_AUDIT_OPENED",
    "SMS_CORRECTIVE_ACTION_CLOSED",
    "SMS_HAZARD_REPORTED",
    "SMS_MITIGATION_IMPLEMENTED",
    "SMS_RISK_ASSESSED",
]
