"""ePCR <-> MAR medication reconciliation contracts.

Typed request/response shapes for the medication-reconciliation API that
reconciles the medications documented on an ePCR chart against the medications
recorded in the system MAR for a single encounter.

Source of truth (mirror — keep in sync; do not diverge silently):
    Adaptix-Medications-Service, merged in PR #173
    (commit ``e035f5b781a50a7afba279010c4de11610de40bc``):
      - ``backend/medications/api/epcr_reconciliation_routes.py`` — request
        models (``EpcrMedItem``, ``EpcrReconciliationCreateRequest``,
        ``EpcrReconciliationResolveRequest``) and the ``_serialize`` response body.
      - ``backend/medications/models.py`` — ``EPCRMedicationReconciliationModel``
        (``reconciliation_status`` values ``pending | in_progress | complete |
        discrepancy``; ``resolution_action`` values ``manual_correction |
        auto_correction | waived``).

Endpoints these contracts describe (mounted at ``/api/v1/medications``):
    POST /epcr-reconciliation                              -> EpcrReconciliationResponse (201)
    GET  /epcr-reconciliation                              -> EpcrReconciliationListResponse
    GET  /epcr-reconciliation/{reconciliation_id}          -> EpcrReconciliationResponse
    POST /epcr-reconciliation/{reconciliation_id}/resolve  -> EpcrReconciliationResponse

Contract-only: data shapes and enums exactly as the service accepts/returns.
No discrepancy-computation or persistence logic is defined here (that stays in
Adaptix-Medications-Service).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EpcrReconciliationStatus(str, Enum):
    """Lifecycle status of an ePCR<->MAR reconciliation session.

    Mirrors ``EPCRMedicationReconciliationModel.reconciliation_status``
    (default ``pending``). ``create`` persists ``discrepancy`` when differences
    are found, else ``in_progress``; ``resolve`` sets ``complete``.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    DISCREPANCY = "discrepancy"


class EpcrDiscrepancyType(str, Enum):
    """Discrepancy kinds emitted by ``compute_epcr_discrepancies``.

    The service compares dose/route/frequency on identity-matched pairs.
    (The DB column comment additionally names ``timing_mismatch``, which the
    current reconciliation route does not emit; it is intentionally omitted here
    to match the values the endpoint actually produces.)
    """

    MISSING_FROM_EPCR = "missing_from_epcr"
    MISSING_FROM_MAR = "missing_from_mar"
    DOSE_MISMATCH = "dose_mismatch"


class EpcrResolutionAction(str, Enum):
    """Action a clinician records when resolving a reconciliation session.

    Mirrors the server-side ``_VALID_RESOLUTION_ACTIONS`` allow-list and the
    ``EPCRMedicationReconciliationModel.resolution_action`` column.
    """

    MANUAL_CORRECTION = "manual_correction"
    AUTO_CORRECTION = "auto_correction"
    WAIVED = "waived"


class EpcrMedItem(BaseModel):
    """One medication line from an ePCR chart or the system MAR.

    ``name`` is always required; ``rxnorm_code`` is the preferred identity when
    present. Comparable fields are dose / route / frequency.
    """

    name: str = Field(min_length=1, max_length=500)
    rxnorm_code: Optional[str] = Field(default=None, max_length=50)
    dose: Optional[str] = Field(default=None, max_length=100)
    route: Optional[str] = Field(default=None, max_length=50)
    frequency: Optional[str] = Field(default=None, max_length=100)
    administered_at: Optional[str] = Field(
        default=None,
        max_length=64,
        description="ISO-8601 administration time, if known.",
    )


class EpcrReconciliationCreateRequest(BaseModel):
    """Request body for ``POST /api/v1/medications/epcr-reconciliation``.

    The caller supplies both medication lists; the service computes discrepancies
    and persists a tenant-scoped session. ``tenant_id`` and ``created_by`` are
    taken from the authenticated context, not the body.
    """

    epcr_chart_id: str = Field(min_length=1, max_length=255)
    patient_id: str = Field(min_length=1, max_length=255)
    encounter_id: Optional[str] = Field(default=None, max_length=255)
    medications_from_epcr: list[EpcrMedItem] = Field(default_factory=list)
    medications_from_mar: list[EpcrMedItem] = Field(default_factory=list)


class EpcrReconciliationResolveRequest(BaseModel):
    """Request body for
    ``POST /api/v1/medications/epcr-reconciliation/{reconciliation_id}/resolve``.
    """

    resolution_action: EpcrResolutionAction
    resolution_notes: Optional[str] = Field(default=None, max_length=2000)


class EpcrFieldDiff(BaseModel):
    """Per-field difference for a ``dose_mismatch`` discrepancy.

    Carries the raw (un-normalized) ePCR and MAR values for one compared field
    (one of dose / route / frequency).
    """

    epcr: Optional[str] = None
    mar: Optional[str] = None


class EpcrReconciliationDiscrepancy(BaseModel):
    """A single computed discrepancy in a reconciliation session.

    ``field_diffs`` is present only for ``dose_mismatch`` entries and is keyed by
    the compared field name (dose / route / frequency).
    """

    type: EpcrDiscrepancyType
    identity_key: str
    epcr: Optional[EpcrMedItem] = None
    mar: Optional[EpcrMedItem] = None
    field_diffs: Optional[dict[str, EpcrFieldDiff]] = None


class EpcrReconciliationResponse(BaseModel):
    """Serialized ePCR reconciliation session (the ``_serialize`` response body).

    Returned by create, get-by-id, and resolve; also the element type of the
    list response.
    """

    reconciliation_id: str
    tenant_id: str
    epcr_chart_id: str
    encounter_id: Optional[str] = None
    patient_id: str
    reconciliation_status: EpcrReconciliationStatus
    medications_from_epcr: list[EpcrMedItem] = Field(default_factory=list)
    medications_from_mar: list[EpcrMedItem] = Field(default_factory=list)
    has_discrepancies: bool
    discrepancies: list[EpcrReconciliationDiscrepancy] = Field(default_factory=list)
    # Comma-joined, sorted set of discrepancy types present (e.g.
    # "dose_mismatch,missing_from_mar"), or None when the session is clean.
    discrepancy_type: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_date: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    resolution_action: Optional[EpcrResolutionAction] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EpcrReconciliationListResponse(BaseModel):
    """Response body for the list endpoint
    ``GET /api/v1/medications/epcr-reconciliation``.
    """

    tenant_id: str
    reconciliations: list[EpcrReconciliationResponse] = Field(default_factory=list)
    generated_at: datetime
