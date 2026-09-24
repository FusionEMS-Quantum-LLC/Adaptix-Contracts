"""Blood Ops event names and payloads.

Producer: Adaptix-Inventory-Service (service-registry slug ``inventory``),
which owns agency inventory and therefore the blood units it holds. The event
names are members of the existing inventory vocabulary,
:class:`adaptix_contracts.inventory_events.InventoryEventType`, and follow the
``inventory.<entity>.<action>`` form the Inventory service already emits; the
constants below read them from there instead of restating them.

* ``inventory.blood_unit.custody_recorded`` - one unit lifecycle transition.
  The payload is :class:`~adaptix_contracts.blood_ops.models.BloodUnitCustodyEvent`.
* ``inventory.blood_excursion.state_changed`` - one cold-chain episode changed
  state. The payload is :class:`BloodColdChainExcursionStateChangedPayload`.
"""

from __future__ import annotations

from typing import Final

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from adaptix_contracts.inventory_events import InventoryEventType

from .lifecycle import (
    COLD_CHAIN_DETECTION_STATES,
    ColdChainExcursionState,
    validate_cold_chain_excursion_transition,
)
from .models import (
    MAX_UNITS_PER_EXCURSION,
    BloodOpsId,
    BloodOpsModel,
    BloodUnitCustodyEvent,
)

BLOOD_OPS_UNIT_CUSTODY_RECORDED: Final[str] = (
    InventoryEventType.BLOOD_UNIT_CUSTODY_RECORDED.value
)
BLOOD_OPS_EXCURSION_STATE_CHANGED: Final[str] = (
    InventoryEventType.BLOOD_EXCURSION_STATE_CHANGED.value
)

BLOOD_OPS_SOURCE_SERVICE: Final[str] = "inventory"
"""Service-registry slug of the producer."""

#: States an episode can only reach by a person's review decision.
_REVIEW_STATES: Final[frozenset[ColdChainExcursionState]] = frozenset(
    {ColdChainExcursionState.RELEASED, ColdChainExcursionState.DISCARDED}
)


class BloodColdChainExcursionStateChangedPayload(BloodOpsModel):  # pylint: disable=too-few-public-methods
    """Payload of ``inventory.blood_excursion.state_changed``.

    ``from_state`` is ``None`` only for the event that opens the episode,
    whose ``to_state`` is ``EXCURSION_DETECTED`` or ``SENSOR_FAILURE`` and
    whose ``excursion_version`` is 1. A detection may be made by a sensor
    (``actor_user_id`` ``None``); a release or a discard is always a
    person's decision and names the ``actor_user_id``.
    """

    tenant_id: BloodOpsId
    excursion_id: BloodOpsId
    storage_location_id: BloodOpsId
    affected_blood_unit_ids: tuple[BloodOpsId, ...] = Field(
        default=(), max_length=MAX_UNITS_PER_EXCURSION
    )
    from_state: ColdChainExcursionState | None
    to_state: ColdChainExcursionState
    actor_user_id: BloodOpsId | None = None
    detection_reading_id: BloodOpsId | None = None
    excursion_version: int = Field(..., ge=1, strict=True)
    occurred_at: AwareDatetime
    correlation_id: BloodOpsId
    idempotency_key: BloodOpsId

    @model_validator(mode="after")
    def validate_change(self) -> BloodColdChainExcursionStateChangedPayload:
        """A published change must be a permitted one with its evidence."""

        if self.from_state is None:
            if self.to_state not in COLD_CHAIN_DETECTION_STATES:
                raise ValueError(
                    "an episode opens as EXCURSION_DETECTED or SENSOR_FAILURE, "
                    f"not {self.to_state.value}"
                )
            if self.excursion_version != 1:
                raise ValueError(
                    "the event that opens an episode has excursion_version 1"
                )
            if self.detection_reading_id is None:
                raise ValueError(
                    "the event that opens an episode names detection_reading_id"
                )
        else:
            if self.from_state is ColdChainExcursionState.NORMAL:
                raise ValueError("an open episode is never NORMAL")
            validate_cold_chain_excursion_transition(self.from_state, self.to_state)
            if self.excursion_version < 2:
                raise ValueError("a later episode event has excursion_version >= 2")
        if self.to_state in _REVIEW_STATES and self.actor_user_id is None:
            raise ValueError(
                f"{self.to_state.value} is a person's decision; name actor_user_id"
            )
        if (
            self.to_state is ColdChainExcursionState.DISCARDED
            and not self.affected_blood_unit_ids
        ):
            raise ValueError("a DISCARDED episode names the units it discards")
        return self


#: Event type -> the payload model a consumer validates it with.
BLOOD_OPS_EVENT_PAYLOADS: Final[dict[str, type[BaseModel]]] = {
    BLOOD_OPS_UNIT_CUSTODY_RECORDED: BloodUnitCustodyEvent,
    BLOOD_OPS_EXCURSION_STATE_CHANGED: BloodColdChainExcursionStateChangedPayload,
}


__all__ = [
    "BLOOD_OPS_EVENT_PAYLOADS",
    "BLOOD_OPS_EXCURSION_STATE_CHANGED",
    "BLOOD_OPS_SOURCE_SERVICE",
    "BLOOD_OPS_UNIT_CUSTODY_RECORDED",
    "BloodColdChainExcursionStateChangedPayload",
]
