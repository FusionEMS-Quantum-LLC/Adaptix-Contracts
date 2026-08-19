"""Contract tests for the tenant capability registry (shared platform primitive I)."""

from __future__ import annotations

from adaptix_contracts.auth.capability_registry import (
    CAPABILITY_REGISTRY,
    PlatformCapability,
    UnknownCapabilityError,
    capabilities_for_module,
    capability_codes,
    is_capability_entitled,
    module_for_capability,
    require_capability,
    resolve_capability,
)
from adaptix_contracts.auth.module_entitlement_gate import (
    require_capability_entitlement,
)
from adaptix_contracts.module_registry import MODULE_REGISTRY
import pytest


class TestRegistryIntegrity:
    def test_every_capability_names_a_canonical_module(self) -> None:
        """An unresolvable module makes the capability permanently unreachable."""

        for capability in CAPABILITY_REGISTRY.values():
            assert capability.module_id in MODULE_REGISTRY, capability.capability_code

    def test_every_capability_code_is_namespaced(self) -> None:
        for code in capability_codes():
            namespace, _, feature = code.partition(".")
            assert namespace, code
            assert feature, code

    def test_codes_are_unique(self) -> None:
        assert len(CAPABILITY_REGISTRY) == len(capability_codes())

    def test_the_registry_is_read_only(self) -> None:
        with pytest.raises(TypeError):
            CAPABILITY_REGISTRY["epcr.made_up"] = PlatformCapability(  # type: ignore[index]
                capability_code="epcr.made_up",
                module_id="epcr",
                display_name="Made up",
                play="P00",
            )

    def test_every_capability_records_its_play(self) -> None:
        for capability in CAPABILITY_REGISTRY.values():
            assert capability.play.startswith("P")


class TestResolution:
    def test_a_registered_code_resolves(self) -> None:
        assert module_for_capability("epcr.ambient_capture") == "epcr"

    def test_resolve_returns_none_for_an_unknown_code(self) -> None:
        assert resolve_capability("epcr.does_not_exist") is None

    def test_require_raises_for_an_unknown_code(self) -> None:
        with pytest.raises(UnknownCapabilityError):
            require_capability("epcr.does_not_exist")

    def test_the_error_is_a_key_error_subclass(self) -> None:
        """Existing `except KeyError` handlers keep working."""

        assert issubclass(UnknownCapabilityError, KeyError)

    def test_capabilities_can_be_listed_per_module(self) -> None:
        assert capabilities_for_module("billing") == {
            "billing.revenue_twin",
            "billing.rsnat_prior_auth",
        }

    def test_a_module_with_no_capabilities_returns_empty(self) -> None:
        assert capabilities_for_module("crm") == frozenset()


class TestEntitlement:
    def test_the_owning_module_entitles_the_capability(self) -> None:
        assert is_capability_entitled("epcr.ambient_capture", ["epcr"])

    def test_an_unrelated_module_does_not(self) -> None:
        assert not is_capability_entitled("epcr.ambient_capture", ["cad"])

    def test_no_entitlements_at_all_does_not(self) -> None:
        assert not is_capability_entitled("epcr.ambient_capture", [])
        assert not is_capability_entitled("epcr.ambient_capture", None)

    def test_a_legacy_alias_still_entitles(self) -> None:
        """Resolution runs through expand_entitlements, exactly like a module gate."""

        assert is_capability_entitled("billing.revenue_twin", ["billing_automation"])

    def test_a_bundle_implication_entitles(self) -> None:
        """nemsis_neris implies neris, which is what fire.neris is gated on."""

        assert is_capability_entitled("fire.neris", ["nemsis_neris"])

    def test_the_fire_module_alone_does_not_entitle_neris(self) -> None:
        """NERIS is its own module; buying Fire is not buying NERIS."""

        assert not is_capability_entitled("fire.neris", ["fire"])

    def test_the_fire_module_does_entitle_the_occupancy_twin(self) -> None:
        assert is_capability_entitled("fire.digital_twin", ["fire"])

    def test_the_crr_module_implies_fire(self) -> None:
        assert is_capability_entitled("fire.digital_twin", ["crr"])

    def test_an_unregistered_capability_fails_closed(self) -> None:
        """A code nobody defined is not a code everybody has."""

        assert not is_capability_entitled("agent.protected_execution", ["core"])
        assert not is_capability_entitled("edge.apparatus", ["device"])
        assert not is_capability_entitled("interop.qhin", ["interoperability"])


class TestGateIntegration:
    def test_a_capability_gate_is_constructible(self) -> None:
        gate = require_capability_entitlement("narcotics.controlled_substances")
        assert callable(gate)

    def test_the_gate_is_named_for_its_capability(self) -> None:
        gate = require_capability_entitlement("billing.rsnat_prior_auth")
        assert (
            gate.__name__ == "require_capability_entitlement_billing_rsnat_prior_auth"
        )

    def test_an_unknown_capability_fails_loudly_at_construction(self) -> None:
        """A route gated on an undefined capability is a route gated on nothing."""

        with pytest.raises(UnknownCapabilityError):
            require_capability_entitlement("epcr.not_a_real_capability")

    def test_every_registered_capability_produces_a_gate(self) -> None:
        for code in sorted(capability_codes()):
            assert callable(require_capability_entitlement(code))


def test_the_module_gate_surface_is_unchanged() -> None:
    """The capability gate is additive; it must not displace the module gate."""

    from adaptix_contracts.auth import module_entitlement_gate

    for name in (
        "require_module_entitlement",
        "require_any_module_entitlement",
        "AUDIT_ACTION",
    ):
        assert hasattr(module_entitlement_gate, name)
