"""Tri-state compliance fact vocabulary (5.27.0).

Shared by every source service that evaluates a compliance fact for an
encounter (for example a vehicle's inspection, a crew member's credential or
a shift assignment at the time of service). Each owner defines its own
per-fact contract later; this module fixes only the status vocabulary and the
result envelope so every consumer reads them the same way.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ComplianceFactStatus(str, Enum):
    """Outcome of evaluating one compliance fact.

    ``UNKNOWN`` covers every case where the fact could not be evaluated: the
    source system was unavailable, timed out, returned no record, or the fact
    is not evaluable for this encounter. A missing upstream response MUST be
    reported as ``UNKNOWN``, never ``INVALID``; ``INVALID`` is reserved for an
    authoritative answer that the fact did not hold.
    """

    VALID = "VALID"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class ComplianceFactResult(BaseModel):
    """One evaluated compliance fact, with provenance.

    ``as_of`` is the service timestamp the fact was evaluated against (the
    encounter time), and ``evaluated_at`` is when the evaluation ran. Both must
    be timezone-aware. ``source_system`` / ``source_record_id`` /
    ``source_version`` identify the owning record the answer came from.
    ``reason`` is a short machine or operator explanation and must never carry
    PHI.
    """

    model_config = ConfigDict(extra="forbid")

    status: ComplianceFactStatus
    evaluated_at: AwareDatetime
    as_of: AwareDatetime
    source_system: str = Field(..., min_length=1)
    source_record_id: Optional[str] = Field(default=None, min_length=1)
    source_version: Optional[str] = Field(default=None, min_length=1)
    reason: Optional[str] = Field(default=None, max_length=500)
