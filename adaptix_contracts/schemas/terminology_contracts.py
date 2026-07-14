"""Concept Intelligence terminology contracts (shared, versioned).

Phase 2 of the Concept Intelligence Platform: the shared DTO surface for the
Terminology + Graph-intelligence concept layer, so consumers (EPCR, Billing,
Medications, NEMSIS, NERIS, Graph, Cortex, ...) stop flattening concepts into
loose code strings.

These are transport/API contracts — NOT the Terminology-Service ORM models. They
mirror the Phase-1 persistence shapes (Adaptix ``concept_id`` identity; UMLS CUI
carried as ``authority`` + ``authority_identifier``; provenance-bearing mappings)
and carry an explicit ``schema_version`` on top-level envelopes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Controlled vocabularies (mirror terminology_app.concept_models)
# ---------------------------------------------------------------------------


class ConceptType(str, Enum):
    CLINICAL = "clinical"
    SYMPTOM = "symptom"
    SIGN = "sign"
    DIAGNOSIS = "diagnosis"
    FINDING = "finding"
    PROCEDURE = "procedure"
    MEDICATION = "medication"
    INGREDIENT = "ingredient"
    DRUG_PRODUCT = "drug_product"
    DEVICE = "device"
    ANATOMY = "anatomy"
    LABORATORY = "laboratory"
    VITAL_SIGN = "vital_sign"
    INJURY = "injury"
    MECHANISM_OF_INJURY = "mechanism_of_injury"
    TRANSPORT_REASON = "transport_reason"
    MEDICAL_NECESSITY = "medical_necessity"
    PROTOCOL = "protocol"
    CARE_PATHWAY = "care_pathway"
    OPERATIONAL = "operational"
    FACILITY = "facility"
    PAYER = "payer"
    DOCUMENTATION_REQUIREMENT = "documentation_requirement"
    NEMSIS_ELEMENT = "nemsis_element"
    NERIS_ELEMENT = "neris_element"
    BILLING_CODE_CONCEPT = "billing_code_concept"


class ConceptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    MERGED = "merged"
    SPLIT = "split"
    REPLACED = "replaced"
    INVALID = "invalid"


class TermType(str, Enum):
    PREFERRED = "preferred"
    SYNONYM = "synonym"
    ABBREVIATION = "abbreviation"
    ACRONYM = "acronym"
    LAY_TERM = "lay_term"
    CLINICAL_PHRASE = "clinical_phrase"
    DEPRECATED_TERM = "deprecated_term"
    MISSPELLING = "misspelling"
    REGIONAL_EXPRESSION = "regional_expression"
    EMS_EXPRESSION = "ems_expression"
    BILLING_EXPRESSION = "billing_expression"
    PATIENT_REPORTED_EXPRESSION = "patient_reported_expression"


class MappingType(str, Enum):
    EXACT = "exact"
    EQUIVALENT = "equivalent"
    BROADER = "broader"
    NARROWER = "narrower"
    RELATED = "related"
    SUPPORTS = "supports"
    REQUIRES_CONTEXT = "requires_context"
    WORKFLOW_ONLY = "workflow_only"
    LOCAL_OVERRIDE = "local_override"
    DEPRECATED = "deprecated"


class MappingDirection(str, Enum):
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"


class ReleaseStatus(str, Enum):
    REGISTERED = "registered"
    IMPORTING = "importing"
    VALIDATED = "validated"
    ACTIVATION_PENDING = "activation_pending"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"
    RETIRED = "retired"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    ESCALATED = "escalated"


class LicenseStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    LICENSE_REQUIRED = "license_required"
    ACTIVE = "active"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class AssertionStatus(str, Enum):
    PRESENT = "present"
    NEGATED = "negated"
    POSSIBLE = "possible"
    CONDITIONAL = "conditional"
    HISTORICAL = "historical"
    RESOLVED = "resolved"
    FAMILY_HISTORY = "family_history"
    PLANNED = "planned"
    ORDERED = "ordered"
    ADMINISTERED = "administered"
    REFUSED = "refused"
    UNKNOWN = "unknown"


class Temporality(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    RECENT = "recent"
    FUTURE = "future"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class Experiencer(str, Enum):
    PATIENT = "patient"
    FAMILY_MEMBER = "family_member"
    CREW_MEMBER = "crew_member"
    OTHER = "other"
    UNKNOWN = "unknown"


class Certainty(str, Enum):
    CONFIRMED = "confirmed"
    SUSPECTED = "suspected"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    UNKNOWN = "unknown"


class MatchReason(str, Enum):
    EXACT_PREFERRED = "exact_preferred"
    EXACT_SYNONYM = "exact_synonym"
    EXACT_CODE = "exact_code"
    ABBREVIATION = "abbreviation"
    PREFIX = "prefix"
    FUZZY = "fuzzy"
    NORMALIZED = "normalized"


class CrosswalkClassification(str, Enum):
    SOURCE_ASSERTED = "source_asserted"
    DETERMINISTIC_LOCAL = "deterministic_local"
    LICENSED_MAPPING = "licensed_mapping"
    CANDIDATE_INFERRED = "candidate_inferred"
    HUMAN_VERIFIED = "human_verified"


class TerminologyEventType(str, Enum):
    CONCEPT_CREATED = "terminology.concept.created"
    CONCEPT_UPDATED = "terminology.concept.updated"
    CONCEPT_DEPRECATED = "terminology.concept.deprecated"
    CONCEPT_MERGED = "terminology.concept.merged"
    CONCEPT_SPLIT = "terminology.concept.split"
    MAPPING_CREATED = "terminology.mapping.created"
    MAPPING_UPDATED = "terminology.mapping.updated"
    MAPPING_RETIRED = "terminology.mapping.retired"
    SOURCE_IMPORTED = "terminology.source.imported"
    SOURCE_ACTIVATED = "terminology.source.activated"
    REVIEW_REQUIRED = "terminology.review.required"
    REVIEW_COMPLETED = "terminology.review.completed"
    RESOLUTION_COMPLETED = "terminology.resolution.completed"


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TerminologySource(_Base):
    source_id: UUID
    canonical_name: str
    short_name: Optional[str] = None
    authority: Optional[str] = None
    source_type: Optional[str] = None
    license_required: bool = False
    license_status: LicenseStatus = LicenseStatus.UNKNOWN
    status: str = "active"
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)


class SourceRelease(_Base):
    release_id: UUID
    source_id: UUID
    version: str
    release_date: Optional[datetime] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    status: ReleaseStatus = ReleaseStatus.REGISTERED
    checksum: Optional[str] = None
    content_location: Optional[str] = None
    activated_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)


class Concept(_Base):
    concept_id: UUID
    authority: str
    authority_identifier: Optional[str] = Field(
        None, description="External authority id, e.g. a UMLS CUI. Never the PK."
    )
    preferred_name: str
    normalized_name: str
    definition: Optional[str] = None
    concept_type: ConceptType
    language: str = "en"
    status: ConceptStatus = ConceptStatus.ACTIVE
    is_clinically_sensitive: bool = False
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    tenant_id: Optional[UUID] = Field(
        None, description="Set for tenant-local concepts; null/nil = global authority."
    )
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)


class ConceptTerm(_Base):
    term_id: UUID
    concept_id: UUID
    text: str
    normalized_text: str
    term_type: TermType
    language: str = "en"
    source_id: Optional[UUID] = None
    source_release_id: Optional[UUID] = None
    source_identifier: Optional[str] = None
    is_preferred: bool = False
    is_abbreviation: bool = False
    is_case_sensitive: bool = False
    status: str = "active"


class SemanticType(_Base):
    semantic_type_id: UUID
    type_identifier: str = Field(..., description="e.g. UMLS 'T184'")
    display_name: str
    authority: str = "UMLS"


class TerminologyCode(_Base):
    terminology_code_id: UUID
    source_system: str
    code: str
    display: Optional[str] = None
    normalized_display: Optional[str] = None
    source_release_id: Optional[UUID] = None
    status: str = "active"
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class CodeMapping(_Base):
    mapping_id: UUID
    concept_id: UUID
    terminology_code_id: UUID
    source_system: Optional[str] = None
    code: Optional[str] = None
    mapping_type: MappingType
    mapping_direction: MappingDirection = MappingDirection.UNIDIRECTIONAL
    authority: str
    confidence: Optional[float] = None
    status: str = "active"
    classification: Optional[CrosswalkClassification] = None
    provenance: dict[str, Any] = Field(
        ..., description="Non-empty. No mapping without provenance (spec §3.6)."
    )
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED

    @field_validator("provenance")
    @classmethod
    def _provenance_non_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError(
                "CodeMapping.provenance must be a non-empty object — an empty "
                "object is not provenance (spec §3.6)."
            )
        return value


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class EvidenceSpan(_Base):
    section: Optional[str] = None
    text: str
    start: int
    end: int


class AssertionContext(_Base):
    assertion: AssertionStatus = AssertionStatus.PRESENT
    temporality: Temporality = Temporality.CURRENT
    experiencer: Experiencer = Experiencer.PATIENT
    certainty: Certainty = Certainty.CONFIRMED


class ConfidenceBreakdown(_Base):
    lexical_match_confidence: float = 0.0
    semantic_match_confidence: float = 0.0
    context_confidence: float = 0.0
    assertion_confidence: float = 0.0
    mapping_confidence: float = 0.0
    workflow_confidence: float = 0.0
    overall_confidence: float = 0.0
    formula_version: str = "1.0"


class ConceptCandidate(_Base):
    concept_id: Optional[UUID] = None
    authority: str = "UMLS"
    authority_identifier: Optional[str] = None
    preferred_name: str
    match_reason: MatchReason
    score: float
    semantic_types: list[str] = Field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    assertion: Optional[AssertionContext] = None
    confidence: Optional[ConfidenceBreakdown] = None
    mappings: list[CodeMapping] = Field(default_factory=list)


class ConceptResolutionRequest(_Base):
    text: str
    workflow: Optional[str] = None
    tenant_id: Optional[UUID] = None
    language: str = "en"
    target_systems: list[str] = Field(default_factory=list)
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)


class ConceptResolutionResponse(_Base):
    original_text: str
    candidates: list[ConceptCandidate] = Field(default_factory=list)
    source_releases: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool = False
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)


# ---------------------------------------------------------------------------
# Autocode
# ---------------------------------------------------------------------------


class AutocodeMappingCandidate(_Base):
    system: str
    code: str
    display: Optional[str] = None
    status: str = "candidate"
    confidence: float = 0.0
    requires_review: bool = True


class AutocodeConcept(_Base):
    concept_id: Optional[UUID] = None
    authority_identifier: Optional[str] = None
    preferred_name: str
    assertion: AssertionContext = Field(default_factory=AssertionContext)
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    mappings: list[AutocodeMappingCandidate] = Field(default_factory=list)
    confidence: Optional[ConfidenceBreakdown] = None
    review_required: bool = True
    accepted: bool = False


class AutocodeOutput(_Base):
    document_id: str
    concepts: list[AutocodeConcept] = Field(default_factory=list)
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)


# ---------------------------------------------------------------------------
# Graph intelligence
# ---------------------------------------------------------------------------


class GraphConceptNode(_Base):
    node_id: str
    concept_id: Optional[UUID] = None
    node_type: str
    preferred_name: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphRelationshipProvenance(_Base):
    authority: str
    source_id: Optional[UUID] = None
    source_release_id: Optional[UUID] = None
    method: str
    evidence: list[str] = Field(default_factory=list)
    effective_from: Optional[datetime] = None
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    created_by: Optional[UUID] = None


class GraphRelationship(_Base):
    edge_id: UUID
    from_node_id: str
    to_node_id: str
    relationship: str
    confidence: Optional[float] = None
    provenance: GraphRelationshipProvenance
    status: str = "active"
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)


class GraphRelationshipExplanation(_Base):
    edge_id: UUID
    source_node: GraphConceptNode
    target_node: GraphConceptNode
    relationship: str
    authority: str
    evidence: list[str] = Field(default_factory=list)
    source_release: Optional[str] = None
    effective_from: Optional[datetime] = None
    confidence: Optional[float] = None
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    created_by: Optional[UUID] = None
    change_history: list[dict[str, Any]] = Field(default_factory=list)
    rule_id: Optional[str] = None
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)


# ---------------------------------------------------------------------------
# Events (envelope shape; runtime registry wiring is Phase 9)
# ---------------------------------------------------------------------------


class TerminologyEventEnvelope(_Base):
    event_id: UUID
    event_type: TerminologyEventType
    schema_version: str = Field(_SCHEMA_VERSION, max_length=16)
    occurred_at: datetime
    producer: str = "terminology"
    concept_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    trace_id: Optional[str] = None
    actor: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
