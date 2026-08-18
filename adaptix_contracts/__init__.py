"""Adaptix contracts package containing shared cross-domain schema definitions.

This package provides typed contract definitions for cross-domain communication
across the Adaptix polyrepo platform.

Import patterns:
    # Import all schemas
    from adaptix_contracts.schemas import *

    # Import specific schemas
    from adaptix_contracts.schemas import (
        ClaimContract,
        EpcrChartCreatedEvent,
        TransportRequestCreate,
    )
"""

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from adaptix_contracts import schemas as _schemas

# Static re-export surface for type checkers (runtime uses globals().update below).
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adaptix_contracts.schemas import *  # noqa: F401,F403

# Redundant aliases mark these as intentional re-exports (suppresses F401
# without requiring entries in __all__, which preserves the package surface
# invariant checked by test_contract_surface.py).
from adaptix_contracts.schemas.legal_execution_contracts import (
    ContractAccessCheckRequest as ContractAccessCheckRequest,
    ContractAccessCheckResponse as ContractAccessCheckResponse,
    ContractSignatureEvent as ContractSignatureEvent,
    ContractStatus as ContractStatus,
    ContractType as ContractType,
    TenantContractStatusMap as TenantContractStatusMap,
)
from adaptix_contracts.event_contracts import (
    BILLING_SERVICE_CONSUMER as BILLING_SERVICE_CONSUMER,
    CAD_SERVICE_CONSUMER as CAD_SERVICE_CONSUMER,
    EPCR_SERVICE_CONSUMER as EPCR_SERVICE_CONSUMER,
    EventMetadata as EventMetadata,
    EventSchema as EventSchema,
    EventValidator as EventValidator,
    HOSPITAL_SERVICE_CONSUMER as HOSPITAL_SERVICE_CONSUMER,
    KNOWN_EVENT_BUS_CONSUMERS as KNOWN_EVENT_BUS_CONSUMERS,
    KnownEventBusConsumerName as KnownEventBusConsumerName,
    LocalEventConsumerRegistry as LocalEventConsumerRegistry,
    is_known_event_bus_consumer as is_known_event_bus_consumer,
)

# Expose the Adaptix Edge apparatus compute node subpackage (Play P23) as an
# attribute of the top-level package so ``adaptix_contracts.edge`` resolves
# without a separate ``import adaptix_contracts.edge`` in downstream code.
# NOT added to ``__all__`` — that surface deliberately mirrors
# ``schemas.__all__`` (see
# ``tests/test_contract_surface.py::test_package_root_reexports_schema_symbols``).
from adaptix_contracts import edge as edge  # noqa: F401


def _resolve_version() -> str:
    """Resolve the package version from installed metadata or ``pyproject.toml``."""

    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject_path.exists():
        project_config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return str(project_config["project"]["version"])

    try:
        return version("adaptix-contracts")
    except PackageNotFoundError:
        raise RuntimeError(
            "adaptix-contracts version metadata is unavailable and pyproject.toml "
            "could not be found beside the source tree"
        ) from None


__version__ = _resolve_version()

# Re-export all schema symbols at package level for convenience.
__all__ = list(_schemas.__all__)
_missing_exports = [name for name in __all__ if not hasattr(_schemas, name)]
if _missing_exports:
    raise ImportError(
        "adaptix_contracts.schemas.__all__ includes missing exports: "
        + ", ".join(sorted(_missing_exports))
    )

globals().update({name: getattr(_schemas, name) for name in _schemas.__all__})

del _schemas
