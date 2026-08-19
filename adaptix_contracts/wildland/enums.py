"""Enums for the Adaptix Wildland federal sync service (Play P10).

Wildland covers Adaptix's sync surface with the federal wildland fire
systems: IROC (Interagency Resource Ordering Capability, resource
ordering/status), IRWIN (Integrated Reporting of Wildland-Fire
Information, incident identity), and WFDSS (Wildland Fire Decision
Support System, strategic decisions). These enums name the shapes those
three systems require without adopting their wire formats verbatim.
"""

from __future__ import annotations

from enum import StrEnum


class IrocResourceType(StrEnum):
    """IROC resource kind ordered/tracked through a resource order.

    Mirrors the coarse resource categories IROC orders move through
    dispatch; ``other`` covers a kind Josh has approved for a specific
    order that does not yet warrant its own member — an order stamped
    ``other`` must still carry a truthful ``resource_type_detail`` on the
    :class:`~adaptix_contracts.wildland.models.IrocResourceOrder` contract.
    """

    CREW = "crew"
    ENGINE = "engine"
    AIRCRAFT = "aircraft"
    OVERHEAD = "overhead"
    EQUIPMENT = "equipment"
    SUPPLY = "supply"
    OTHER = "other"


class WfdssPhase(StrEnum):
    """Lifecycle phase of a WFDSS strategic decision.

    ``draft`` covers analysis in progress before a decision is published;
    ``published`` and ``revised`` are the states line personnel act on;
    ``archived`` is terminal for a superseded decision.
    """

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    PUBLISHED = "published"
    REVISED = "revised"
    ARCHIVED = "archived"


class Ics209Section(StrEnum):
    """Named section of an ICS-209 Incident Status Summary report.

    Sections mirror the federal ICS-209 form structure so a partial
    report (one section filed ahead of the rest) can be represented
    without inventing a parallel field taxonomy.
    """

    INCIDENT_SUMMARY = "incident_summary"
    CURRENT_SITUATION = "current_situation"
    RESOURCE_COMMITMENT = "resource_commitment"
    PROJECTED_ACTIVITY = "projected_activity"
    STRATEGIC_DISCUSSION = "strategic_discussion"
    THREAT_SUMMARY = "threat_summary"
    COMMAND = "command"


__all__ = [
    "Ics209Section",
    "IrocResourceType",
    "WfdssPhase",
]
