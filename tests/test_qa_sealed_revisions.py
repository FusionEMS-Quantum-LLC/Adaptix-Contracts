"""Contract tests for ePCR's eligible sealed-revision pages (every-chart coverage)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from adaptix_contracts.qa import (
    QA_SEALED_REVISIONS_READ_SCOPE,
    SEALED_REVISION_PAGE_MAX,
    SEALED_REVISION_PAGE_VERSION,
    SEALED_REVISIONS_PATH,
    SealedRevisionExclusions,
    SealedRevisionPage,
    SealedRevisionRef,
)

FROM = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)
TO = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
NO_EXCLUSIONS = SealedRevisionExclusions(
    legacy_backfill=0, non_production=0, deleted_chart=0
)


def _ref(
    version_id: str = "sv-1",
    sealed_at: datetime = FROM + timedelta(hours=1),
    **overrides: object,
) -> SealedRevisionRef:
    values: dict[str, object] = {
        "chart_id": "chart-1",
        "signed_version_id": version_id,
        "signed_version_number": 1,
        "sealed_at": sealed_at,
        "is_amendment": False,
        "is_current": True,
    }
    values.update(overrides)
    return SealedRevisionRef.model_validate(values)


def _page(
    *refs: SealedRevisionRef, eligible_total: int | None = None, **overrides: object
) -> SealedRevisionPage:
    values: dict[str, object] = {
        "tenant_id": "tenant-1",
        "sealed_from": FROM,
        "sealed_to": TO,
        "eligible_total": len(refs) if eligible_total is None else eligible_total,
        "exclusions": NO_EXCLUSIONS,
        "revisions": refs,
    }
    values.update(overrides)
    return SealedRevisionPage.model_validate(values)


def test_a_valid_page_round_trips_through_json() -> None:
    page = _page(
        _ref("sv-1"),
        _ref("sv-2", FROM + timedelta(hours=2), is_current=False),
        eligible_total=7,
        exclusions=SealedRevisionExclusions(
            legacy_backfill=3, non_production=1, deleted_chart=2
        ),
        next_cursor="opaque-position",
    )

    restored = SealedRevisionPage.model_validate_json(page.model_dump_json())

    assert restored == page
    assert restored.page_version == SEALED_REVISION_PAGE_VERSION == "1.0"
    assert [ref.signed_version_id for ref in restored.revisions] == ["sv-1", "sv-2"]
    assert restored.exclusions.legacy_backfill == 3


def test_the_route_constants_are_pinned() -> None:
    # The producer (ePCR) and the consumer (QA) both import these; a change is
    # a breaking contract change and must be deliberate.
    assert QA_SEALED_REVISIONS_READ_SCOPE == "qa-sealed-revisions:read"
    assert SEALED_REVISIONS_PATH == "/api/v1/epcr/internal/qa/sealed-revisions"
    assert SEALED_REVISION_PAGE_MAX == 500


def test_a_naive_timestamp_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ref(sealed_at=datetime(2026, 10, 6, 1, 0))
    with pytest.raises(ValidationError):
        _page(sealed_from=datetime(2026, 10, 6, 0, 0))


def test_the_window_must_move_forward() -> None:
    with pytest.raises(ValidationError, match="earlier than sealed_to"):
        _page(sealed_from=TO, sealed_to=TO)
    with pytest.raises(ValidationError, match="earlier than sealed_to"):
        _page(sealed_from=TO, sealed_to=FROM)


def test_the_window_includes_its_start_and_excludes_its_end() -> None:
    assert _page(_ref(sealed_at=FROM)).revisions[0].sealed_at == FROM
    with pytest.raises(ValidationError, match="outside the window"):
        _page(_ref(sealed_at=TO))
    with pytest.raises(ValidationError, match="outside the window"):
        _page(_ref(sealed_at=FROM - timedelta(microseconds=1)))


def test_revisions_must_be_strictly_ascending_without_repeats() -> None:
    first = _ref("sv-a", FROM + timedelta(hours=2))
    second = _ref("sv-b", FROM + timedelta(hours=1))
    with pytest.raises(ValidationError, match="strictly ascending"):
        _page(first, second)
    with pytest.raises(ValidationError, match="strictly ascending"):
        _page(first, first)


def test_equal_seal_times_order_by_signed_version_id() -> None:
    same = FROM + timedelta(hours=3)
    page = _page(_ref("sv-a", same), _ref("sv-b", same))
    assert [ref.signed_version_id for ref in page.revisions] == ["sv-a", "sv-b"]
    with pytest.raises(ValidationError, match="strictly ascending"):
        _page(_ref("sv-b", same), _ref("sv-a", same))


def test_a_page_cannot_exceed_its_eligible_total_or_the_page_maximum() -> None:
    with pytest.raises(ValidationError, match="eligible_total"):
        _page(_ref("sv-1"), _ref("sv-2", FROM + timedelta(hours=2)), eligible_total=1)
    too_many = tuple(
        _ref(f"sv-{index:04d}", FROM + timedelta(seconds=index))
        for index in range(SEALED_REVISION_PAGE_MAX + 1)
    )
    with pytest.raises(ValidationError):
        _page(*too_many)
    assert len(_page(*too_many[:SEALED_REVISION_PAGE_MAX]).revisions) == 500


def test_counts_and_identifiers_are_bounded() -> None:
    with pytest.raises(ValidationError):
        SealedRevisionExclusions(legacy_backfill=-1, non_production=0, deleted_chart=0)
    with pytest.raises(ValidationError):
        _page(eligible_total=-1)
    with pytest.raises(ValidationError):
        _ref(signed_version_number=0)
    with pytest.raises(ValidationError):
        _ref(chart_id="")
    with pytest.raises(ValidationError):
        _page(next_cursor="")


def test_unknown_fields_are_refused() -> None:
    with pytest.raises(ValidationError):
        _ref(patient_name="never part of this contract")
    with pytest.raises(ValidationError):
        _page(chart_content="never part of this contract")


def test_an_empty_last_page_is_valid() -> None:
    page = _page(eligible_total=0)
    assert page.revisions == ()
    assert page.next_cursor is None
