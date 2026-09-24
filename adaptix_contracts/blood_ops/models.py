"""Blood Ops records: the unit, its custody events, cold-chain readings and episodes.

Reuse
-----
Product category, ABO group and Rh factor are the shared blood-bank
vocabulary in :mod:`adaptix_contracts.cct.enums` (``BloodProductType``,
``AboGroup``, ``RhFactor``), and the label fields keep the names the CCT
``BloodProduct`` contract already uses (``isbt128_code``, ``product_code``,
``issuing_facility_name`` / ``issuing_facility_id``). They are imported, never
redefined: two definitions of one wire value is the worse defect.

CCT's ``BloodProduct`` is a unit carried on ONE interfacility mission and
issued to that crew. A Blood Ops unit is agency inventory: it enters agency
custody, is stored, assigned to apparatus, and ends transfused, returned or
destroyed. The CCT ``unit_id`` (the label's Donation Identification Number)
is ``donation_identification_number`` here, because on an EMS apparatus
"unit" already means the vehicle.

Boundaries
----------
* Identity is by platform user id only (``actor_user_id``,
  ``witness_user_id``); no printed names travel in these records.
* A transfusion references the ePCR chart (``chart_id``) that documents it,
  which is the traceability a blood bank's recipient lookback needs. No
  patient demographics are carried.
* ``tenant_id`` is always resolved server-side from the verified caller; a
  consumer never trusts a tenant supplied in a request body.
* ``version`` / ``unit_version`` / ``excursion_version`` are optimistic
  concurrency versions. ``idempotency_key`` makes a redelivered or
  double-submitted event apply once.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from adaptix_contracts.cct.enums import AboGroup, BloodProductType, RhFactor

from .lifecycle import (
    BLOOD_UNIT_USABLE_STATES,
    COLD_CHAIN_USABLE_STATES,
    BloodUnitLifecycleState,
    ColdChainExcursionState,
    ColdChainReadingClassification,
    validate_blood_unit_transition,
)

#: Identifier or reference in a Blood Ops record: bounded, no control
#: characters.
BloodOpsId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]

#: Operator-entered reason or note. Bounded; never patient content.
BloodOpsNote = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=2000,
        pattern=r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+$",
    ),
]

#: Upper bound on the units one excursion episode can name.
MAX_UNITS_PER_EXCURSION = 500

_Lifecycle = BloodUnitLifecycleState
_Excursion = ColdChainExcursionState


class BloodOpsModel(BaseModel):  # pylint: disable=too-few-public-methods
    """The one base of every Blood Ops record.

    Unknown fields are refused (a producer cannot attach patient
    demographics), no field can be reassigned after validation, and
    surrounding whitespace is stripped from every string.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class BloodUnit(BloodOpsModel):  # pylint: disable=too-few-public-methods
    """One blood unit in an agency's custody, as it stands now.

    Invariants (see :meth:`validate_unit`):

    * a unit that can still reach a patient (``AVAILABLE``, ``ASSIGNED``) has a
      usable cold chain (``NORMAL`` or ``RELEASED``);
    * ``ASSIGNED`` names the apparatus, and only ``ASSIGNED`` does;
    * ``TRANSFUSED`` names the chart that documents it, and only it does;
    * the label expiry is after collection.

    A terminal unit may still carry an open cold-chain status: a logger read
    after a shift can reveal an excursion before a transfusion, and that must
    be recordable for the recipient lookback.
    """

    blood_unit_id: BloodOpsId
    tenant_id: BloodOpsId
    donation_identification_number: BloodOpsId
    isbt128_code: BloodOpsId | None = None
    product_code: BloodOpsId | None = None
    product_type: BloodProductType
    abo_group: AboGroup
    rh_factor: RhFactor
    volume_ml: float | None = Field(
        default=None, ge=0, strict=True, allow_inf_nan=False
    )
    collected_at: AwareDatetime | None = None
    expires_at: AwareDatetime
    issuing_facility_name: BloodOpsId
    issuing_facility_id: BloodOpsId | None = None
    received_at: AwareDatetime
    lifecycle_state: BloodUnitLifecycleState
    cold_chain_state: ColdChainExcursionState
    storage_location_id: BloodOpsId | None = None
    assigned_apparatus_id: BloodOpsId | None = None
    transfused_chart_id: BloodOpsId | None = None
    version: int = Field(..., ge=1, strict=True)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_unit(self) -> BloodUnit:
        """Enforce the safety and traceability invariants of a unit."""

        if self.collected_at is not None and self.expires_at <= self.collected_at:
            raise ValueError("expires_at must be after collected_at")
        if (
            self.lifecycle_state in BLOOD_UNIT_USABLE_STATES
            and self.cold_chain_state not in COLD_CHAIN_USABLE_STATES
        ):
            raise ValueError(
                f"a {self.lifecycle_state.value} unit cannot have cold chain "
                f"{self.cold_chain_state.value}; quarantine it first"
            )
        assigned = self.lifecycle_state is _Lifecycle.ASSIGNED
        if assigned != (self.assigned_apparatus_id is not None):
            raise ValueError(
                "assigned_apparatus_id is set exactly when the unit is ASSIGNED"
            )
        transfused = self.lifecycle_state is _Lifecycle.TRANSFUSED
        if transfused != (self.transfused_chart_id is not None):
            raise ValueError(
                "transfused_chart_id is set exactly when the unit is TRANSFUSED"
            )
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        return self


class BloodUnitCustodyEvent(BloodOpsModel):  # pylint: disable=too-few-public-methods
    """One lifecycle transition of one unit, and who was accountable for it.

    Every change of ``lifecycle_state`` is a custody event; the unit's
    history is the ordered list of these, and none is ever edited.

    * ``from_state`` is ``None`` only when the unit enters agency custody
      (``to_state`` ``RECEIVED``, ``unit_version`` 1).
    * ``unit_version`` is the unit's ``version`` after this event.
    * ``TRANSFUSED`` names the ``chart_id`` and a ``witness_user_id`` who is
      not the ``actor_user_id``: the two-person check at the bedside, the
      same rule the CCT service enforces at infusion.
    * ``ASSIGNED`` names ``to_apparatus_id``; ``RETURNED`` names
      ``to_facility_id``; ``QUARANTINED`` and ``DESTROYED`` state a
      ``reason``.
    """

    custody_event_id: BloodOpsId
    tenant_id: BloodOpsId
    blood_unit_id: BloodOpsId
    from_state: BloodUnitLifecycleState | None
    to_state: BloodUnitLifecycleState
    unit_version: int = Field(..., ge=1, strict=True)
    occurred_at: AwareDatetime
    recorded_at: AwareDatetime
    actor_user_id: BloodOpsId
    witness_user_id: BloodOpsId | None = None
    from_location_id: BloodOpsId | None = None
    to_location_id: BloodOpsId | None = None
    to_apparatus_id: BloodOpsId | None = None
    to_facility_id: BloodOpsId | None = None
    chart_id: BloodOpsId | None = None
    excursion_id: BloodOpsId | None = None
    reason: BloodOpsNote | None = None
    correlation_id: BloodOpsId
    idempotency_key: BloodOpsId

    @model_validator(mode="after")
    def validate_custody(self) -> BloodUnitCustodyEvent:
        """A custody event must be a permitted transition with its evidence."""

        validate_blood_unit_transition(self.from_state, self.to_state)
        if (self.from_state is None) != (self.unit_version == 1):
            raise ValueError(
                "unit_version is 1 exactly for the event that receives the unit"
            )
        if (
            self.witness_user_id is not None
            and self.witness_user_id == self.actor_user_id
        ):
            raise ValueError("the witness must be a second person, not the actor")
        target = self.to_state
        if target is _Lifecycle.TRANSFUSED:
            if self.chart_id is None:
                raise ValueError(
                    "a TRANSFUSED event names the chart_id that documents it"
                )
            if self.witness_user_id is None:
                raise ValueError("a TRANSFUSED event requires a witness_user_id")
        if target is _Lifecycle.ASSIGNED and self.to_apparatus_id is None:
            raise ValueError("an ASSIGNED event names to_apparatus_id")
        if target is _Lifecycle.RETURNED and self.to_facility_id is None:
            raise ValueError("a RETURNED event names to_facility_id")
        if (
            target in {_Lifecycle.QUARANTINED, _Lifecycle.DESTROYED}
            and self.reason is None
        ):
            raise ValueError(f"a {target.value} event states its reason")
        return self


class BloodColdChainReading(BloodOpsModel):  # pylint: disable=too-few-public-methods
    """One temperature reading of one storage location, as classified.

    ``storage_profile_id`` names the configured storage profile (acceptable
    band) the producing service classified the reading against; the band
    itself is not a contract value. A ``SENSOR_FAILURE`` reading has no
    ``temperature_c``; every other reading has one. A manual reading
    (``sensor_id`` ``None``) names who took it and cannot be a sensor
    failure.
    """

    reading_id: BloodOpsId
    tenant_id: BloodOpsId
    storage_location_id: BloodOpsId
    sensor_id: BloodOpsId | None = None
    recorded_by_user_id: BloodOpsId | None = None
    storage_profile_id: BloodOpsId
    classification: ColdChainReadingClassification
    temperature_c: float | None = Field(default=None, strict=True, allow_inf_nan=False)
    recorded_at: AwareDatetime
    idempotency_key: BloodOpsId

    @model_validator(mode="after")
    def validate_reading(self) -> BloodColdChainReading:
        """A reading states a temperature exactly when one was measured."""

        failed = self.classification is ColdChainReadingClassification.SENSOR_FAILURE
        if failed and self.temperature_c is not None:
            raise ValueError("a SENSOR_FAILURE reading has no temperature_c")
        if not failed and self.temperature_c is None:
            raise ValueError(
                f"a {self.classification.value} reading carries temperature_c"
            )
        if self.sensor_id is None:
            if self.recorded_by_user_id is None:
                raise ValueError("a manual reading names recorded_by_user_id")
            if failed:
                raise ValueError("a manual reading cannot be a SENSOR_FAILURE")
        return self


class BloodColdChainExcursion(BloodOpsModel):  # pylint: disable=too-few-public-methods
    """One cold-chain episode at one storage location, from detection to review.

    An episode opens at ``EXCURSION_DETECTED`` or ``SENSOR_FAILURE`` and ends
    ``RELEASED`` or ``DISCARDED``; it is never ``NORMAL``. Both endings are a
    person's decision, so they name ``reviewed_by_user_id`` and
    ``reviewed_at``. ``DISCARDED`` names at least one affected unit.
    """

    excursion_id: BloodOpsId
    tenant_id: BloodOpsId
    storage_location_id: BloodOpsId
    affected_blood_unit_ids: tuple[BloodOpsId, ...] = Field(
        default=(), max_length=MAX_UNITS_PER_EXCURSION
    )
    state: ColdChainExcursionState
    detection_reading_id: BloodOpsId
    detected_at: AwareDatetime
    reviewed_by_user_id: BloodOpsId | None = None
    reviewed_at: AwareDatetime | None = None
    review_note: BloodOpsNote | None = None
    version: int = Field(..., ge=1, strict=True)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_episode(self) -> BloodColdChainExcursion:
        """An episode's state and its review evidence must agree."""

        if self.state is _Excursion.NORMAL:
            raise ValueError("an excursion episode is never NORMAL")
        if len(set(self.affected_blood_unit_ids)) != len(self.affected_blood_unit_ids):
            raise ValueError("affected_blood_unit_ids must not repeat a unit")
        reviewed = self.state in {_Excursion.RELEASED, _Excursion.DISCARDED}
        if reviewed != (
            self.reviewed_by_user_id is not None and self.reviewed_at is not None
        ):
            raise ValueError(
                "reviewed_by_user_id and reviewed_at are set exactly when the "
                "episode is RELEASED or DISCARDED"
            )
        if self.state is _Excursion.DISCARDED and not self.affected_blood_unit_ids:
            raise ValueError("a DISCARDED episode names the units it discards")
        if self.reviewed_at is not None and self.reviewed_at < self.detected_at:
            raise ValueError("reviewed_at precedes detected_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        return self


__all__ = [
    "MAX_UNITS_PER_EXCURSION",
    "BloodColdChainExcursion",
    "BloodColdChainReading",
    "BloodOpsId",
    "BloodOpsModel",
    "BloodOpsNote",
    "BloodUnit",
    "BloodUnitCustodyEvent",
]
