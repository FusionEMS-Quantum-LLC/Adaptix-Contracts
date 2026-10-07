"""Eligible sealed chart revisions: what every-chart review must account for.

Adaptix-EPCR-Service owns sealing, so ePCR decides which sealed revisions a
period holds and answers them as :class:`SealedRevisionPage`. Adaptix-QA-Service
compares the list with its review ledger:

* a current revision with no completed review is reviewed by reconciliation;
* a revision an amendment has since superseded is recorded superseded;
* coverage is reported as accounted-for against eligible, for the same period.

Eligibility
-----------
A sealed revision is eligible when all of these hold:

* it was sealed (``sealed_at`` set) inside ``[sealed_from, sealed_to)``;
* it was sealed by signature. A legacy backfill seal (a chart finalized before
  sealing existed, sealed later from retained evidence) is counted as an
  exclusion. Whether historical charts are reviewed retroactively is a product
  decision, so they are neither silently included nor silently dropped;
* the chart is a production record. A synthetic WARDS Lab chart never enters QA;
* the chart is not deleted.

Every exclusion is counted for the same window
(:class:`SealedRevisionExclusions`), and ``eligible_total`` counts every
eligible revision across all pages. A reader can therefore prove it received
the whole list, and nothing leaves the count unexplained.

Paging
------
Keyset on ``(sealed_at, signed_version_id)``, ascending. Each page is validated
to be strictly ordered, inside the window and without repeats, and
``next_cursor`` is ePCR's opaque position after the last revision returned. For
a window that has already closed (``sealed_to`` in the past) the population is
fixed: a seal made now carries ``sealed_at`` = now, outside the window.

PHI
---
Identifiers, version numbers, timestamps and counts only. No chart content.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

#: Shape version of :class:`SealedRevisionPage`. Bump on any breaking change.
SEALED_REVISION_PAGE_VERSION: Final[Literal["1.0"]] = "1.0"

#: The most revisions ePCR answers on one page; QA asks for at most this many.
SEALED_REVISION_PAGE_MAX: Final[int] = 500

#: The pinned service-token scope of ePCR's sealed-revisions route.
QA_SEALED_REVISIONS_READ_SCOPE: Final[str] = "qa-sealed-revisions:read"

#: ePCR's internal route that answers :class:`SealedRevisionPage`. Query
#: parameters: ``sealed_from`` and ``sealed_to`` (ISO 8601 with an offset;
#: ``sealed_to`` exclusive), ``after`` (a ``next_cursor``) and ``limit``
#: (1 to :data:`SEALED_REVISION_PAGE_MAX`).
SEALED_REVISIONS_PATH: Final[str] = "/api/v1/epcr/internal/qa/sealed-revisions"


class SealedRevisionRef(BaseModel):
    """One eligible sealed revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chart_id: str = Field(..., min_length=1, max_length=64)
    signed_version_id: str = Field(..., min_length=1, max_length=64)
    signed_version_number: int = Field(..., ge=1)
    sealed_at: AwareDatetime
    is_amendment: bool
    #: Still the chart's latest sealed revision. A revision an amendment has
    #: superseded is accounted for by recording it superseded, not by review.
    is_current: bool


class SealedRevisionExclusions(BaseModel):
    """Sealed revisions in the same window that are not eligible, by reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    legacy_backfill: int = Field(..., ge=0)
    non_production: int = Field(..., ge=0)
    deleted_chart: int = Field(..., ge=0)


class SealedRevisionPage(BaseModel):
    """One keyset page of a tenant's eligible sealed revisions for a window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_version: Literal["1.0"] = SEALED_REVISION_PAGE_VERSION
    tenant_id: str = Field(..., min_length=1, max_length=64)
    sealed_from: AwareDatetime
    #: Exclusive.
    sealed_to: AwareDatetime
    #: Eligible revisions in the whole window, across every page.
    eligible_total: int = Field(..., ge=0)
    exclusions: SealedRevisionExclusions
    revisions: tuple[SealedRevisionRef, ...] = Field(
        ..., max_length=SEALED_REVISION_PAGE_MAX
    )
    #: Pass back as ``after`` for the next page; None on the last page.
    next_cursor: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def _ordered_inside_the_window(self) -> SealedRevisionPage:
        if self.sealed_from >= self.sealed_to:
            raise ValueError("sealed_from must be earlier than sealed_to")
        if len(self.revisions) > self.eligible_total:
            raise ValueError("a page cannot hold more revisions than eligible_total")
        previous: tuple[datetime, str] | None = None
        for ref in self.revisions:
            if not self.sealed_from <= ref.sealed_at < self.sealed_to:
                raise ValueError(
                    f"revision {ref.signed_version_id} was sealed outside the window"
                )
            key = (ref.sealed_at, ref.signed_version_id)
            if previous is not None and key <= previous:
                raise ValueError(
                    "revisions must be strictly ascending by "
                    "(sealed_at, signed_version_id) without repeats"
                )
            previous = key
        return self


__all__ = [
    "QA_SEALED_REVISIONS_READ_SCOPE",
    "SEALED_REVISIONS_PATH",
    "SEALED_REVISION_PAGE_MAX",
    "SEALED_REVISION_PAGE_VERSION",
    "SealedRevisionExclusions",
    "SealedRevisionPage",
    "SealedRevisionRef",
]
