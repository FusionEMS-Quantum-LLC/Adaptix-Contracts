"""Search and indexing contracts.

Defines typed contracts for cross-domain search, indexing, filtering,
and result aggregation across all Adaptix services.

This layer enables unified query across billing, epcr, cad, transport,
and all other domains without tight coupling.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SearchDomain(str, Enum):
    """Domains that can be searched."""

    BILLING = "billing"
    EPCR = "epcr"
    CAD = "cad"
    FIRE = "fire"
    TRANSPORT = "transport"
    CREW = "crew"
    PATIENT = "patient"
    DOCUMENT = "document"
    ALL = "all"


class SearchResultType(str, Enum):
    """Type classification for search results."""

    CLAIM = "claim"
    PATIENT = "patient"
    CHART = "chart"
    INCIDENT = "incident"
    TRANSPORT_REQUEST = "transport_request"
    TRIP = "trip"
    DOCUMENT = "document"
    CREW_MEMBER = "crew_member"
    OTHER = "other"


class SearchSortOrder(str, Enum):
    """Sorting options for search results."""

    RELEVANCE = "relevance"
    NEWEST = "newest"
    OLDEST = "oldest"


# ---------------------------------------------------------------------------
# Request Contracts
# ---------------------------------------------------------------------------


class SearchQueryRequest(BaseModel):
    """Cross-domain search query request."""

    tenant_id: str

    query: str = Field(..., min_length=1, max_length=500)

    domains: list[SearchDomain] = Field(default_factory=lambda: [SearchDomain.ALL])

    filters: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value filters (e.g. status=denied, payer=medicare)",
    )

    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    sort_order: SearchSortOrder = SearchSortOrder.RELEVANCE

    requested_by_user_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Result Contracts
# ---------------------------------------------------------------------------


class SearchResultItem(BaseModel):
    """Single search result item."""

    result_id: str
    tenant_id: str

    result_type: SearchResultType
    domain: SearchDomain

    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None

    reference_id: Optional[str] = None
    reference_type: Optional[str] = None

    score: float = Field(..., ge=0.0)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    """Search response containing result set."""

    query: str
    tenant_id: str

    total_count: int
    limit: int
    offset: int

    results: list[SearchResultItem]

    executed_at: datetime


# ---------------------------------------------------------------------------
# Indexing Contracts
# ---------------------------------------------------------------------------


class IndexDocumentRequest(BaseModel):
    """Request to index a document into search."""

    tenant_id: str

    document_id: str
    domain: SearchDomain
    result_type: SearchResultType

    title: str
    content: str

    metadata: dict[str, str] = Field(default_factory=dict)

    indexed_at: datetime


class IndexDocumentResponse(BaseModel):
    """Response after indexing a document."""

    document_id: str
    indexed: bool
    message: Optional[str] = None
    indexed_at: datetime


class DeleteIndexDocumentRequest(BaseModel):
    """Request to remove a document from search index."""

    tenant_id: str
    document_id: str


class DeleteIndexDocumentResponse(BaseModel):
    """Response after deleting a document from index."""

    document_id: str
    deleted: bool
    deleted_at: datetime


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class SearchExecutedEvent(BaseModel):
    """Published when a search query is executed."""

    event_type: str = "search.query.executed"

    tenant_id: str
    query: str
    result_count: int

    executed_at: datetime


class DocumentIndexedEvent(BaseModel):
    """Published when a document is indexed."""

    event_type: str = "search.document.indexed"

    tenant_id: str
    document_id: str
    domain: SearchDomain

    indexed_at: datetime


class DocumentDeletedEvent(BaseModel):
    """Published when a document is removed from index."""

    event_type: str = "search.document.deleted"

    tenant_id: str
    document_id: str

    deleted_at: datetime
