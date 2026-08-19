"""Contract tests for uniform human confirmation (shared platform primitive B)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from adaptix_contracts import schemas
from adaptix_contracts.schemas.human_confirmation_contracts import (
    DECIDED_DISPOSITIONS,
    HumanConfirmationReceipt,
    HumanDisposition,
    is_decided,
)
import pytest
from pydantic import ValidationError

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=5)


def _receipt(**overrides: object) -> HumanConfirmationReceipt:
    payload: dict[str, object] = {
        "receipt_id": "rcpt-1",
        "tenant_id": "tenant-a",
        "subject_type": "epcr_narrative",
        "subject_id": "chart-1",
        "disposition": HumanDisposition.GENERATED,
        "generated_by": "model-exec-1",
        "generated_at": NOW,
        "expected_state_version": 4,
    }
    payload.update(overrides)
    return HumanConfirmationReceipt(**payload)  # type: ignore[arg-type]


class TestDecidedDispositions:
    @pytest.mark.parametrize(
        "disposition",
        [
            HumanDisposition.ACCEPTED,
            HumanDisposition.EDITED,
            HumanDisposition.REJECTED,
        ],
    )
    def test_decided_dispositions_report_true(
        self, disposition: HumanDisposition
    ) -> None:
        assert is_decided(disposition)

    @pytest.mark.parametrize(
        "disposition",
        [
            HumanDisposition.GENERATED,
            HumanDisposition.PRESENTED,
            HumanDisposition.EXPIRED,
        ],
    )
    def test_undecided_dispositions_report_false(
        self, disposition: HumanDisposition
    ) -> None:
        assert not is_decided(disposition)

    def test_expired_is_not_a_decision(self) -> None:
        """An expiry is the absence of a decision, never a silent approval."""

        assert HumanDisposition.EXPIRED not in DECIDED_DISPOSITIONS

    def test_unknown_disposition_fails_closed(self) -> None:
        assert not is_decided("rubber_stamped")

    def test_every_disposition_is_classified(self) -> None:
        for disposition in HumanDisposition:
            assert isinstance(is_decided(disposition), bool)


class TestReceiptInvariants:
    def test_generated_receipt_needs_no_decider(self) -> None:
        assert _receipt().decided_by is None

    def test_accepted_receipt_requires_a_decider(self) -> None:
        with pytest.raises(ValidationError, match="decided_by, decided_at is missing"):
            _receipt(disposition=HumanDisposition.ACCEPTED)

    def test_accepted_receipt_requires_a_decision_time(self) -> None:
        with pytest.raises(ValidationError, match="decided_at is missing"):
            _receipt(disposition=HumanDisposition.ACCEPTED, decided_by="user-1")

    def test_accepted_receipt_with_a_real_human_is_valid(self) -> None:
        receipt = _receipt(
            disposition=HumanDisposition.ACCEPTED,
            decided_by="user-1",
            decided_at=LATER,
        )
        assert is_decided(receipt.disposition)

    def test_expired_receipt_may_not_carry_a_decider(self) -> None:
        """A timed-out proposal must never look like somebody approved it."""

        with pytest.raises(ValidationError, match="not a human decision"):
            _receipt(
                disposition=HumanDisposition.EXPIRED,
                decided_by="user-1",
                decided_at=LATER,
            )

    def test_edited_receipt_requires_the_delta_hash(self) -> None:
        with pytest.raises(ValidationError, match="must carry edit_delta_hash"):
            _receipt(
                disposition=HumanDisposition.EDITED,
                decided_by="user-1",
                decided_at=LATER,
            )

    def test_edited_receipt_with_a_delta_hash_is_valid(self) -> None:
        receipt = _receipt(
            disposition=HumanDisposition.EDITED,
            decided_by="user-1",
            decided_at=LATER,
            edit_delta_hash="sha256:delta",
        )
        assert receipt.edit_delta_hash == "sha256:delta"

    def test_delta_hash_on_an_accepted_receipt_is_refused(self) -> None:
        """Accepted means unchanged; a delta says otherwise."""

        with pytest.raises(ValidationError, match="only meaningful on an EDITED"):
            _receipt(
                disposition=HumanDisposition.ACCEPTED,
                decided_by="user-1",
                decided_at=LATER,
                edit_delta_hash="sha256:delta",
            )

    def test_decision_may_not_predate_generation(self) -> None:
        with pytest.raises(ValidationError, match="decided_at precedes generated_at"):
            _receipt(
                disposition=HumanDisposition.ACCEPTED,
                decided_by="user-1",
                decided_at=NOW - timedelta(minutes=1),
            )

    def test_presentation_may_not_predate_generation(self) -> None:
        with pytest.raises(ValidationError, match="presented_at precedes generated_at"):
            _receipt(presented_at=NOW - timedelta(minutes=1))

    def test_expected_state_version_is_required(self) -> None:
        """No default: a receipt must pin the version the person actually saw."""

        assert HumanConfirmationReceipt.model_fields[
            "expected_state_version"
        ].is_required()

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _receipt(narrative_text="never store this here")


def test_surface_is_exported_from_the_package_root() -> None:
    for name in (
        "HumanConfirmationReceipt",
        "HumanDisposition",
        "DECIDED_DISPOSITIONS",
    ):
        assert name in schemas.__all__
        assert hasattr(schemas, name)
