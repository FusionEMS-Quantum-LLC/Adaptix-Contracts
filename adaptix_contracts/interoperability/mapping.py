"""Versioned semantic mapping contracts between source standards and canonical data."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MappingType(str, Enum):
    """How a source field relates to the canonical field it maps to.

    ``NO_EQUIVALENT`` and ``MANUAL_REVIEW`` are first-class members on
    purpose: a mapping set has to be able to state that a source field has no
    canonical home, or that a person must decide, rather than forcing a wrong
    ``DIRECT`` mapping and losing the fact that the value was never really
    translated.
    """

    DIRECT = "DIRECT"
    NORMALIZED = "NORMALIZED"
    CONDITIONAL = "CONDITIONAL"
    DERIVED = "DERIVED"
    NO_EQUIVALENT = "NO_EQUIVALENT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class SemanticMappingRule(BaseModel):  # pylint: disable=too-few-public-methods
    """One versioned rule translating a source path to a canonical path.

    Versioned rather than global: ``source_standard`` and ``source_version``
    pin what the rule reads, ``effective_from`` and ``deprecated_at`` bound
    when it applied, and ``mapping_rule_id`` is the identifier
    :class:`~adaptix_contracts.interoperability.provenance.DataProvenance`
    cites — so a value translated last year can still be explained by the
    rule that was in force when it was translated. ``mapping_type`` records
    whether a translation happened at all; ``confidence`` and ``conditions``
    qualify it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    mapping_rule_id: str = Field(..., min_length=1)
    mapping_set_id: str = Field(..., min_length=1)
    source_standard: str = Field(..., min_length=1)
    source_version: str = Field(..., min_length=1)
    source_path: str = Field(..., min_length=1)
    canonical_path: str = Field(..., min_length=1)
    target_standard: str | None = None
    target_version: str | None = None
    target_path: str | None = None
    mapping_type: MappingType
    transform: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    conditions: dict[str, Any] = Field(default_factory=dict)
    effective_from: datetime
    deprecated_at: datetime | None = None
    source_reference: str | None = None


class MappingPreviewResult(BaseModel):  # pylint: disable=too-few-public-methods
    """Result of applying a mapping set without committing anything.

    The buckets stay separate because they need different handling:
    ``mapped`` translated cleanly, ``conditional`` only under a rule's
    conditions, ``unmapped`` matched no rule, and ``blocked`` could not be
    carried through. Collapsing them would hide exactly the cases an operator
    has to resolve before an exchange goes out. ``mapping_evidence`` carries
    the per-value justification and ``warnings`` the non-blocking concerns.
    """

    model_config = ConfigDict(extra="forbid")

    mapped: list[dict[str, Any]] = Field(default_factory=list)
    unmapped: list[dict[str, Any]] = Field(default_factory=list)
    conditional: list[dict[str, Any]] = Field(default_factory=list)
    blocked: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    mapping_evidence: list[dict[str, Any]] = Field(default_factory=list)


__all__ = ["MappingPreviewResult", "MappingType", "SemanticMappingRule"]
