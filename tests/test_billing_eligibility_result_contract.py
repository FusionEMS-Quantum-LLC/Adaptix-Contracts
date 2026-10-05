"""Contract guards for ``billing.eligibility.result.v1`` (directive P6).

Billing owns payer eligibility; ePCR shows a read projection of it. These
tests fix the three properties that make the event safe to publish:

* the payload is the minimum summary and nothing else. Its field set is
  pinned, and the raw 271, the benefit detail and every subscriber identity
  are refused by ``extra="forbid"``;
* the coverage status is a closed set of five, and a result with no payer
  answer behind it can only say ``error``;
* the event is registered with Billing as its producer, under the same
  version the payload declares.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import adaptix_contracts
from adaptix_contracts import schemas
from adaptix_contracts.events.bus_limits import BUS_CORRELATION_ID_MAX_LENGTH
from adaptix_contracts.events.operational_envelope import (
    OperationalEventEnvelope,
    assert_event_type_registered,
)
from adaptix_contracts.events.registry import (
    ALL_EVENTS,
    BILLING_ELIGIBILITY_RESULT_V1 as REGISTRY_EVENT_NAME,
    is_registered,
    producer_of,
)
from adaptix_contracts.schemas.billing_eligibility_result_contracts import (
    BILLING_ELIGIBILITY_RESULT_SCHEMA_VERSION,
    BILLING_ELIGIBILITY_RESULT_SOURCE_SERVICE,
    BILLING_ELIGIBILITY_RESULT_V1,
    ELIGIBILITY_RESULT_ID_MAX_LENGTH,
    ELIGIBILITY_RESULT_UNANSWERED_SOURCES,
    BillingEligibilityResultPayload,
    EligibilityCoverageStatus,
    EligibilityResultSource,
)
from adaptix_contracts.schemas.service_registry import BILLING_SERVICE

TENANT = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
CHECK = "0d4f6f0e-52f1-4a7c-9b1f-3f1d7c0a9e11"
CHART = "c7a1d2e3-0000-4000-8000-00000000c4a7"
CHECKED_AT = datetime(2026, 7, 1, 14, 30, 5, tzinfo=UTC)

#: The content the directive lists, as field names. Adding a field to the
#: payload without changing this set is a red test, on purpose.
DIRECTIVE_CONTENT: frozenset[str] = frozenset(
    {
        "schema_version",
        "tenant_id",
        "chart_id",
        "patient_identity_id",
        "claim_id",
        "eligibility_check_id",
        "clearinghouse_eligibility_id",
        "trading_partner_service_id",
        "payer_id",
        "response_payer_id",
        "coverage_status",
        "coverage_effective_from",
        "coverage_effective_through",
        "checked_at",
        "source",
        "correlation_id",
        "trace_number",
    }
)


def _payload(**overrides: object) -> BillingEligibilityResultPayload:
    values: dict[str, object] = {
        "tenant_id": TENANT,
        "eligibility_check_id": CHECK,
        "payer_id": "60054",
        "coverage_status": "active",
        "checked_at": CHECKED_AT,
        "source": "stedi_271",
    }
    values.update(overrides)
    return BillingEligibilityResultPayload.model_validate(values)


# ---------------------------------------------------------------------------
# Name, producer, version
# ---------------------------------------------------------------------------


def test_the_event_name_is_the_one_the_directive_fixes() -> None:
    assert BILLING_ELIGIBILITY_RESULT_V1 == "billing.eligibility.result.v1"
    assert REGISTRY_EVENT_NAME == BILLING_ELIGIBILITY_RESULT_V1


def test_the_event_is_registered_with_billing_as_its_producer() -> None:
    assert is_registered(BILLING_ELIGIBILITY_RESULT_V1)
    assert BILLING_ELIGIBILITY_RESULT_SOURCE_SERVICE == "billing"
    assert (
        ALL_EVENTS[BILLING_ELIGIBILITY_RESULT_V1]["source_service"]
        == BILLING_ELIGIBILITY_RESULT_SOURCE_SERVICE
    )
    assert producer_of(BILLING_ELIGIBILITY_RESULT_V1) is BILLING_SERVICE


def test_the_registry_version_is_the_payload_schema_version() -> None:
    assert BILLING_ELIGIBILITY_RESULT_SCHEMA_VERSION == "1.0"
    assert (
        ALL_EVENTS[BILLING_ELIGIBILITY_RESULT_V1]["version"]
        == BILLING_ELIGIBILITY_RESULT_SCHEMA_VERSION
    )
    assert _payload().schema_version == BILLING_ELIGIBILITY_RESULT_SCHEMA_VERSION


def test_the_event_passes_the_operational_backbone_gate() -> None:
    envelope = OperationalEventEnvelope(
        event_type=BILLING_ELIGIBILITY_RESULT_V1,
        tenant_id=TENANT,
        source_service=BILLING_ELIGIBILITY_RESULT_SOURCE_SERVICE,
        source_record_id=CHECK,
        source_version=1,
        observed_at=CHECKED_AT,
        effective_at=CHECKED_AT,
    )
    assert_event_type_registered(envelope)


def test_the_contract_is_exported_from_the_schema_surface_and_the_root() -> None:
    for name in (
        "BILLING_ELIGIBILITY_RESULT_SCHEMA_VERSION",
        "BILLING_ELIGIBILITY_RESULT_V1",
        "BillingEligibilityResultPayload",
        "EligibilityCoverageStatus",
        "EligibilityResultSource",
    ):
        assert name in schemas.__all__
        assert getattr(adaptix_contracts, name) is getattr(schemas, name)
    assert schemas.BillingEligibilityResultPayload is BillingEligibilityResultPayload


# ---------------------------------------------------------------------------
# The payload is the minimum summary, and nothing else
# ---------------------------------------------------------------------------


def test_the_payload_carries_exactly_the_content_the_directive_lists() -> None:
    assert set(BillingEligibilityResultPayload.model_fields) == DIRECTIVE_CONTENT


def test_only_what_every_resolved_check_has_is_required() -> None:
    """Everything Billing may not know for a check is optional, never invented."""
    required = {
        name
        for name, field in BillingEligibilityResultPayload.model_fields.items()
        if field.is_required()
    }
    assert required == {
        "tenant_id",
        "eligibility_check_id",
        "payer_id",
        "coverage_status",
        "checked_at",
        "source",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("raw_271", "ISA*00*          *00*          *ZZ*PAYER~ST*271*0001~"),
        ("raw_response", {"planStatus": [{"statusCode": "1"}]}),
        ("x12", "ST*271*0001*005010X279A1~"),
        ("benefits", [{"code": "B", "amount_cents": 2000}]),
        ("benefits_json", [{"code": "1"}]),
        ("benefitsInformation", [{"code": "1"}]),
        ("request_validations", [{"reject_reason_code": "75"}]),
        ("aaa_errors", [{"code": "75"}]),
        ("coverage_dates", [{"qualifier": "291", "value": "20260101-20261231"}]),
        ("plan_description", "GOLD PPO PLAN"),
        ("payer_name", "WISCONSIN MEDICAID"),
        ("member_id", "W123456789"),
        ("subscriber_member_id", "W123456789"),
        ("patient_name", "Doe, Jane"),
        ("first_name", "Jane"),
        ("last_name", "Doe"),
        ("date_of_birth", "1980-01-15"),
        ("patient_id", "5b0f3c1e-8d2a-4c6f-9a31-2f7e4d9b6c10"),
        ("service_date", "20260701"),
        ("error_message", "Payer could not answer the eligibility request"),
        ("copay_cents", 2000),
        ("deductible_remaining_cents", 50000),
    ],
)
def test_the_raw_271_benefits_and_subscriber_identity_are_refused(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError) as refused:
        _payload(**{field: value})
    errors = refused.value.errors()
    assert [error["type"] for error in errors] == ["extra_forbidden"]
    assert errors[0]["loc"] == (field,)


def test_a_serialised_payload_names_only_the_directive_content() -> None:
    original = _payload(
        chart_id=CHART,
        patient_identity_id="5b0f3c1e-8d2a-4c6f-9a31-2f7e4d9b6c10",
        claim_id="2f0a4f52-5a0c-4a52-8a61-6f3f3f0d5c01",
        clearinghouse_eligibility_id="01J1SNT1FQC8P3YHJBW7X1C8XB",
        trading_partner_service_id="60054",
        response_payer_id="60054",
        coverage_effective_from=date(2026, 1, 1),
        coverage_effective_through=date(2026, 12, 31),
        correlation_id="req-1",
        trace_number="000000042",
    )
    wire = original.model_dump(mode="json")

    assert set(wire) == DIRECTIVE_CONTENT
    assert wire["coverage_status"] == "active"
    assert wire["source"] == "stedi_271"
    assert wire["coverage_effective_from"] == "2026-01-01"
    assert wire["coverage_effective_through"] == "2026-12-31"
    assert wire["checked_at"] == "2026-07-01T14:30:05Z"
    assert BillingEligibilityResultPayload.model_validate(wire) == original


def test_what_billing_does_not_know_is_null_not_invented() -> None:
    wire = _payload().model_dump(mode="json")
    for name in (
        "chart_id",
        "patient_identity_id",
        "claim_id",
        "clearinghouse_eligibility_id",
        "trading_partner_service_id",
        "response_payer_id",
        "coverage_effective_from",
        "coverage_effective_through",
        "correlation_id",
        "trace_number",
    ):
        assert wire[name] is None, name


def test_the_payload_is_immutable() -> None:
    payload = _payload()
    with pytest.raises(ValidationError):
        setattr(payload, "coverage_status", EligibilityCoverageStatus.INACTIVE)
    assert payload.coverage_status is EligibilityCoverageStatus.ACTIVE


# ---------------------------------------------------------------------------
# Coverage status and source
# ---------------------------------------------------------------------------


def test_coverage_status_is_the_closed_set_of_five() -> None:
    assert {status.value for status in EligibilityCoverageStatus} == {
        "active",
        "inactive",
        "non_covered",
        "unknown",
        "error",
    }


@pytest.mark.parametrize(
    "not_a_status",
    ["eligible", "covered", "submitted", "not_configured", "ACTIVE", "", "paid"],
)
def test_a_status_outside_the_set_is_refused(not_a_status: str) -> None:
    with pytest.raises(ValidationError):
        _payload(coverage_status=not_a_status)


def test_the_sources_are_the_governed_clearinghouse_sources() -> None:
    assert {source.value for source in EligibilityResultSource} == {
        "stedi_271",
        "stedi_270",
        "office_ally_271",
    }
    assert ELIGIBILITY_RESULT_UNANSWERED_SOURCES == {EligibilityResultSource.STEDI_270}


@pytest.mark.parametrize("status", ["active", "inactive", "non_covered", "unknown"])
def test_a_result_with_no_271_behind_it_cannot_state_coverage(status: str) -> None:
    with pytest.raises(ValidationError, match="no payer answer behind it"):
        _payload(source="stedi_270", coverage_status=status)


def test_a_result_with_no_271_behind_it_is_an_error() -> None:
    payload = _payload(source="stedi_270", coverage_status="error")
    assert payload.coverage_status is EligibilityCoverageStatus.ERROR
    assert payload.source is EligibilityResultSource.STEDI_270


@pytest.mark.parametrize("source", ["stedi_271", "office_ally_271"])
@pytest.mark.parametrize(
    "status", ["active", "inactive", "non_covered", "unknown", "error"]
)
def test_a_271_may_carry_any_of_the_five_statuses(source: str, status: str) -> None:
    payload = _payload(source=source, coverage_status=status)
    assert payload.coverage_status.value == status


def test_an_unknown_source_is_refused() -> None:
    with pytest.raises(ValidationError):
        _payload(source="manual_entry")


# ---------------------------------------------------------------------------
# Version, identifiers, timestamp
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["1.0", "1.1", "1.27"])
def test_any_minor_of_major_one_is_accepted(version: str) -> None:
    assert _payload(schema_version=version).schema_version == version


@pytest.mark.parametrize("version", ["2.0", "0.9", "1", "v1", "1.0.0", "", "1.x"])
def test_another_major_or_a_malformed_version_is_refused(version: str) -> None:
    with pytest.raises(ValidationError):
        _payload(schema_version=version)


@pytest.mark.parametrize("field", ["tenant_id", "eligibility_check_id", "payer_id"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_a_required_identifier_cannot_be_blank(field: str, blank: str) -> None:
    with pytest.raises(ValidationError):
        _payload(**{field: blank})


@pytest.mark.parametrize(
    "field",
    [
        "chart_id",
        "patient_identity_id",
        "claim_id",
        "clearinghouse_eligibility_id",
        "trading_partner_service_id",
        "response_payer_id",
        "trace_number",
    ],
)
def test_an_optional_identifier_is_null_or_real_never_blank_or_oversized(
    field: str,
) -> None:
    assert getattr(_payload(**{field: None}), field) is None
    widest = "x" * ELIGIBILITY_RESULT_ID_MAX_LENGTH
    assert getattr(_payload(**{field: widest}), field) == widest
    with pytest.raises(ValidationError):
        _payload(**{field: "   "})
    with pytest.raises(ValidationError):
        _payload(**{field: widest + "x"})


def test_the_correlation_id_is_bounded_by_the_bus_width() -> None:
    widest = "c" * BUS_CORRELATION_ID_MAX_LENGTH
    assert _payload(correlation_id=widest).correlation_id == widest
    with pytest.raises(ValidationError):
        _payload(correlation_id=widest + "c")


def test_checked_at_must_say_which_instant_it_is() -> None:
    with pytest.raises(ValidationError):
        _payload(checked_at=datetime(2026, 7, 1, 14, 30, 5))
    with pytest.raises(ValidationError):
        _payload(checked_at="2026-07-01T14:30:05")


def test_checked_at_keeps_the_instant_across_offsets() -> None:
    central = timezone(timedelta(hours=-5))
    local = _payload(checked_at=datetime(2026, 7, 1, 9, 30, 5, tzinfo=central))
    assert local.checked_at == CHECKED_AT


def test_coverage_dates_are_calendar_dates() -> None:
    payload = _payload(
        coverage_effective_from="2026-01-01", coverage_effective_through="2026-12-31"
    )
    assert payload.coverage_effective_from == date(2026, 1, 1)
    assert payload.coverage_effective_through == date(2026, 12, 31)
    with pytest.raises(ValidationError):
        _payload(coverage_effective_from="20260101-20261231")
