"""Adaptix encounter lineage — shared cross-domain primitive.

* :mod:`adaptix_contracts.lineage.models` —
  :class:`~adaptix_contracts.lineage.models.EncounterLineage`, the canonical
  dispatch -> transport -> trip -> unit/vehicle/crew -> ePCR -> payer chain of
  opaque identifiers for one encounter.
* :mod:`adaptix_contracts.lineage.compliance` —
  :class:`~adaptix_contracts.lineage.compliance.ComplianceFactStatus`
  (``VALID`` / ``INVALID`` / ``UNKNOWN``) and
  :class:`~adaptix_contracts.lineage.compliance.ComplianceFactResult`.

This package is the shared contract only. Each referenced record stays owned
by its domain service.
"""

from adaptix_contracts.lineage.compliance import (
    ComplianceFactResult,
    ComplianceFactStatus,
)
from adaptix_contracts.lineage.models import EncounterLineage

__all__ = ["ComplianceFactResult", "ComplianceFactStatus", "EncounterLineage"]
