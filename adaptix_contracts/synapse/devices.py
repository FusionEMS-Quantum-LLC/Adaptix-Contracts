"""Device genome and capability profile contracts (SYN-001).

The existing Adaptix-Device-Service ``Device`` row is the canonical physical
identity of a device; there is no second physical-device table. A
:class:`DeviceGenome` describes what that device IS and what it PROVIDES, in
canonical capability terms. Applications never branch on a manufacturer: they
read a :class:`DeviceCapabilityProfile` and ask ``provides(...)``.

Neither model carries a patient field. A device genome describes hardware and
data capability only; patient identity never belongs here, and ``extra`` is
forbidden so none can be attached.

Neither model carries a tenant either. The owning tenant is the persisted
``Device`` row's ``tenant_id``; a producer (adapter, edge instance) never
asserts it, so a genome cannot be used to attribute a device to another tenant.

:class:`DriverPackSupport` records whether a driver pack is enabled and
certified. Optional manufacturer compatibility packs live here as data (an id
such as ``COMPAT-<NAME>-001``), never as a type: nothing above the driver layer
branches on a manufacturer, and no compatibility pack is ever a prerequisite of
a first-party Adaptix capability.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from adaptix_contracts.synapse.enums import (
    EXTERNAL_WAIT_DRIVER_PACK_STATUSES,
    SIGNAL_KIND_REQUIRED_CAPABILITY,
    DriverPackSupportStatus,
    DriverPackTier,
    SynapseDeviceCapability,
    SynapseSignalKind,
    TransportKind,
    is_forbidden_control_capability,
)
from adaptix_contracts.synapse.provenance import (
    AdapterKey,
    DeviceClass,
    DriverPackId,
    IdentityText,
    SemanticVersion,
    Sha256Hex,
    SynapseId,
    SynapseModel,
)

#: Separator used when hashing identity parts. ASCII unit separator cannot
#: appear in a validated identity part, so ``("ab", "c")`` and ``("a", "bc")``
#: can never hash the same.
_IDENTITY_SEPARATOR = "\x1f"


def compute_physical_identity_hash(
    manufacturer: str, model: str, serial_number: str
) -> str:
    """The single definition of a device's physical identity digest.

    SHA-256 over the case-folded, whitespace-trimmed manufacturer, model and
    serial number joined by the ASCII unit separator. Every producer (an
    Integrations adapter, the Device service, a Synapse Edge instance) MUST
    call this function rather than re-derive it, so the same physical device
    always hashes to the same value.
    """

    parts = (manufacturer, model, serial_number)
    normalized = _IDENTITY_SEPARATOR.join(part.strip().casefold() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class DeviceIdentity(SynapseModel):
    """Manufacturer-reported physical identity of one device.

    ``manufacturer`` and ``model`` are recorded facts about the hardware, not
    types: nothing above the adapter boundary branches on them.
    ``physical_identity_hash`` must equal
    :func:`compute_physical_identity_hash` of the three parts; a mismatch is
    rejected so the digest can never drift from the identity it names.
    """

    manufacturer: IdentityText
    model: IdentityText
    serial_number: IdentityText
    physical_identity_hash: Sha256Hex

    @model_validator(mode="after")
    def _hash_matches_identity(self) -> DeviceIdentity:
        expected = compute_physical_identity_hash(
            self.manufacturer, self.model, self.serial_number
        )
        if self.physical_identity_hash != expected:
            raise ValueError(
                "physical_identity_hash does not match manufacturer/model/"
                "serial_number; compute it with compute_physical_identity_hash"
            )
        return self


class DeviceAdapterRef(SynapseModel):
    """The Integrations adapter (connector) that decodes this device."""

    key: AdapterKey
    version: SemanticVersion


def _check_unique(name: str, values: list[Any]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not repeat")


class _DeviceDeclaration(SynapseModel):
    """Fields shared by the genome and the identity-free profile.

    Private base: neither public model subclasses the other, so a genome
    (which carries physical identity) can never be passed where an
    identity-free profile is expected.
    """

    device_id: SynapseId
    genome_version: int = Field(ge=1)
    device_class: DeviceClass
    transports: list[TransportKind] = Field(min_length=1)
    capabilities: list[SynapseDeviceCapability] = Field(min_length=1)
    signals: list[SynapseSignalKind] = Field(min_length=1)
    adapter: DeviceAdapterRef
    last_verified_at: AwareDatetime

    @field_validator("capabilities", mode="before")
    @classmethod
    def _reject_forbidden_control(cls, value: Any) -> Any:
        """Refuse therapy/control vocabulary by name, before enum coercion,
        so certification reports WHY rather than a generic enum error."""

        if isinstance(value, (list, tuple, set, frozenset)):
            forbidden = sorted(
                item
                for item in value
                if isinstance(item, str) and is_forbidden_control_capability(item)
            )
            if forbidden:
                raise ValueError(
                    "therapy/control capabilities are forbidden in Synapse v1 "
                    f"(medical-device command plane): {forbidden}"
                )
        return value

    @model_validator(mode="after")
    def _coherent_declaration(self) -> _DeviceDeclaration:
        _check_unique("transports", list(self.transports))
        _check_unique("capabilities", list(self.capabilities))
        _check_unique("signals", list(self.signals))
        uncovered = sorted(
            kind.value
            for kind in self.signals
            if (required := SIGNAL_KIND_REQUIRED_CAPABILITY[kind]) is not None
            and required not in self.capabilities
        )
        if uncovered:
            raise ValueError(
                "signals declared without the capability they require: "
                f"{uncovered} (see SIGNAL_KIND_REQUIRED_CAPABILITY)"
            )
        return self

    def provides(self, capability: SynapseDeviceCapability) -> bool:
        """True when the device declares ``capability``."""

        return capability in self.capabilities

    def emits(self, signal_kind: SynapseSignalKind) -> bool:
        """True when the device declares it emits ``signal_kind``."""

        return signal_kind in self.signals


class DeviceCapabilityProfile(_DeviceDeclaration):
    """What a device provides, without its physical identity.

    This is the shape applications consume: they ask ``provides(capability)``
    or ``emits(signal_kind)`` and never look at who made the device.
    """


class DeviceGenome(_DeviceDeclaration):
    """The full canonical description of one physical device.

    ``device_id`` is the Device-service ``Device.id``. ``genome_version``
    increases by one on every change so writers can apply optimistic
    concurrency. ``last_verified_at`` is when the adapter last confirmed the
    declaration against the real device. ``identity`` is the only part that
    names the hardware; :meth:`capability_profile` drops it.
    """

    identity: DeviceIdentity

    def capability_profile(self) -> DeviceCapabilityProfile:
        """Project the identity-free profile applications consume."""

        return DeviceCapabilityProfile(
            device_id=self.device_id,
            genome_version=self.genome_version,
            device_class=self.device_class,
            transports=list(self.transports),
            capabilities=list(self.capabilities),
            signals=list(self.signals),
            adapter=self.adapter,
            last_verified_at=self.last_verified_at,
        )


#: Prefix every optional manufacturer compatibility pack id carries.
COMPAT_DRIVER_PACK_PREFIX = "COMPAT-"


class DriverPackSupport(SynapseModel):
    """Enablement and certification status of one Synapse driver pack.

    Rules this contract enforces:

    * ``blocks_core_readiness`` is always ``False``. No driver pack status -
      least of all an optional compatibility pack waiting on an outside party -
      is a prerequisite of a first-party Adaptix capability, and the contract
      cannot express one.
    * A ``FIRST_PARTY`` pack never waits on an outside party: the
      ``WAITING_EXTERNAL_*`` statuses are refused for it.
    * ``OPTIONAL_COMPAT`` pack ids start with ``COMPAT-``; first-party ids
      never do, so the two tiers cannot be confused by id.
    * ``CERTIFIED`` requires the exact adapter version that was certified and
      when. Only a ``CERTIFIED`` pack is :attr:`supported`.
    """

    driver_pack_id: DriverPackId
    tier: DriverPackTier
    status: DriverPackSupportStatus
    adapter: DeviceAdapterRef | None = None
    certified_at: AwareDatetime | None = None
    status_changed_at: AwareDatetime
    blocks_core_readiness: Literal[False] = False

    @model_validator(mode="after")
    def _tier_status_and_certification(self) -> DriverPackSupport:
        is_compat_id = self.driver_pack_id.startswith(COMPAT_DRIVER_PACK_PREFIX)
        if self.tier is DriverPackTier.OPTIONAL_COMPAT and not is_compat_id:
            raise ValueError(
                f"an OPTIONAL_COMPAT pack id must start with {COMPAT_DRIVER_PACK_PREFIX!r}"
            )
        if self.tier is DriverPackTier.FIRST_PARTY:
            if is_compat_id:
                raise ValueError(
                    f"a FIRST_PARTY pack id must not start with {COMPAT_DRIVER_PACK_PREFIX!r}"
                )
            if self.status in EXTERNAL_WAIT_DRIVER_PACK_STATUSES:
                raise ValueError(
                    "a FIRST_PARTY driver pack never waits on an outside party; "
                    f"{self.status.value!r} is only valid for OPTIONAL_COMPAT packs"
                )
        if self.status is DriverPackSupportStatus.CERTIFIED:
            if self.adapter is None or self.certified_at is None:
                raise ValueError(
                    "CERTIFIED requires the certified adapter (key and version) "
                    "and certified_at"
                )
        elif self.certified_at is not None:
            raise ValueError("certified_at is only carried by a CERTIFIED pack")
        return self

    @property
    def supported(self) -> bool:
        """True only for a ``CERTIFIED`` pack. Nothing else may be called supported."""

        return self.status is DriverPackSupportStatus.CERTIFIED


__all__ = [
    "COMPAT_DRIVER_PACK_PREFIX",
    "DeviceAdapterRef",
    "DeviceCapabilityProfile",
    "DeviceGenome",
    "DeviceIdentity",
    "DriverPackSupport",
    "compute_physical_identity_hash",
]
